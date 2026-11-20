import logging
from contextlib import contextmanager
from datetime import timedelta
from io import StringIO
from uuid import UUID

from db.ingestion.cards import media_patch as media_patch, save_cards
from parser.graphql.models import Movie, MovieDetails


_WORKER_LOCK = 723049381
logger = logging.getLogger(__name__)


def _vote_count(movie: Movie) -> int | None:
    if "votes_kp" in movie.loaded_fields:
        return movie.votes_kp
    return movie.rating_kp.votes if movie.rating_kp else None


def votes_above(movie: Movie, threshold: int) -> bool:
    votes = _vote_count(movie)
    return votes is not None and votes > threshold


class IngestionStore:
    def __init__(self, engine, *, log_unchanged: bool = False):
        self.engine = engine
        self.log_unchanged = log_unchanged

    @contextmanager
    def transaction(self):
        connection = self.engine.raw_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL search_path = kinopoisk, pg_catalog")
                cursor.execute("SET LOCAL lock_timeout = '5s'")
                cursor.execute("SET LOCAL statement_timeout = '30s'")
                yield cursor
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def check_schema(self, *, writer: bool = False) -> None:
        required = {'media_ingestion_job': {'media_id'}}
        if writer:
            required.update({
                'media': {'media_id'}, 'person': {'person_id'},
                'role': {'name'}, 'genre': {'name'}, 'country': {'name'},
                'media_person_role': {'media_id', 'person_id', 'role_id'},
                'media_genre': {'media_id', 'genre_id'},
                'media_country': {'media_id', 'country_id'},
                'media_alias': {'media_id', 'name'},
                'media_fact': {'media_id', 'position'},
                'media_recommendation': {'media_id', 'recommended_id'},
                'season': {'media_id', 'season_number'},
                'episode': {'season_id', 'episode_number'},
                'connection_type': {'name'},
                'connected_media': {'media_id', 'parent_id', 'connection_id'},
                'media_ingestion_relation': {'media_id', 'related_media_id', 'connection_id'},
            })
        with self.transaction() as cursor:
            cursor.execute('''
                SELECT c.relname, array_agg(a.attname ORDER BY k.ordinality)
                FROM pg_index i
                JOIN pg_class c ON c.oid = i.indrelid
                JOIN pg_namespace n ON n.oid = c.relnamespace
                CROSS JOIN LATERAL unnest(i.indkey) WITH ORDINALITY k(attnum, ordinality)
                JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = k.attnum
                WHERE n.nspname = 'kinopoisk' AND i.indisunique AND i.indisvalid
                    AND i.indimmediate AND i.indpred IS NULL AND i.indexprs IS NULL
                    AND k.ordinality <= i.indnkeyatts
                GROUP BY c.relname, i.indexrelid
            ''')
            found = {(table, frozenset(columns)) for table, columns in cursor.fetchall()}
        missing = [f'{table}({", ".join(sorted(columns))})'
                   for table, columns in required.items() if (table, frozenset(columns)) not in found]
        if missing:
            raise RuntimeError('Missing unique keys: ' + ', '.join(missing)
                               + '. Check catalog migrations through V008.')

    @contextmanager
    def worker_lock(self):
        connection = self.engine.raw_connection()
        acquired = False
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT pg_try_advisory_lock(%s)', (_WORKER_LOCK,))
                acquired = cursor.fetchone()[0]
            connection.commit()
            if not acquired:
                raise RuntimeError('Another ingestion worker is already running for this database')
            yield
        finally:
            try:
                if acquired:
                    connection.rollback()
                    with connection.cursor() as cursor:
                        cursor.execute('SELECT pg_advisory_unlock(%s)', (_WORKER_LOCK,))
                    connection.commit()
            finally:
                connection.close()

    def enqueue(self, movie_ids, *, source: str, priority: int = 0,
                missing_only: bool = False, force: bool = False) -> int:
        ids = sorted(set(movie_ids))
        if not ids:
            return 0
        if any(type(movie_id) is not int or not 0 < movie_id <= 2147483647 for movie_id in ids):
            raise ValueError('movie IDs must fit a positive PostgreSQL integer')
        with self.transaction() as cursor:
            cursor.execute('CREATE TEMP TABLE discovered_media (media_id integer PRIMARY KEY) ON COMMIT DROP')
            cursor.copy_expert('COPY discovered_media (media_id) FROM STDIN',
                               StringIO(''.join(f'{movie_id}\n' for movie_id in ids)))
            condition = 'WHERE NOT EXISTS (SELECT 1 FROM media m WHERE m.media_id = d.media_id)' if missing_only else ''
            conflict = '''DO UPDATE SET priority = GREATEST(media_ingestion_job.priority, EXCLUDED.priority),
                state = 'pending', attempts = 0, next_attempt_at = now(), last_error = NULL,
                updated_at = now() WHERE media_ingestion_job.state <> 'running' ''' if force else 'DO NOTHING'
            cursor.execute(f'''
                INSERT INTO media_ingestion_job (media_id, source, priority)
                SELECT d.media_id, %s, %s FROM discovered_media d {condition}
                ON CONFLICT (media_id) {conflict}
            ''', (source, priority))
            return cursor.rowcount

    def seed_refresh(self, *, batch_size: int = 5000, force: bool = False) -> int:
        if type(batch_size) is not int or batch_size <= 0:
            raise ValueError('batch_size must be a positive integer')
        last_id = 0
        total = 0
        while True:
            with self.transaction() as cursor:
                cursor.execute('SELECT media_id FROM media WHERE media_id > %s ORDER BY media_id LIMIT %s',
                               (last_id, batch_size))
                ids = [row[0] for row in cursor.fetchall()]
            if not ids:
                return total
            total += self.enqueue(ids, source='refresh', force=force)
            last_id = ids[-1]

    def claim(self, token: UUID, limit: int, *, lease_seconds: float = 120) -> list[tuple[int, int]]:
        with self.transaction() as cursor:
            cursor.execute('''
                WITH ready AS (
                    SELECT media_id, priority, next_attempt_at FROM media_ingestion_job
                    WHERE state = 'pending' AND next_attempt_at <= now()
                    ORDER BY priority DESC, next_attempt_at, media_id
                    FOR UPDATE SKIP LOCKED LIMIT %s
                ), expired AS (
                    SELECT media_id, priority, next_attempt_at FROM media_ingestion_job
                    WHERE state = 'running' AND lease_until <= now()
                    ORDER BY lease_until, media_id
                    FOR UPDATE SKIP LOCKED LIMIT %s
                ), candidates AS (
                    SELECT media_id FROM (SELECT * FROM ready UNION ALL SELECT * FROM expired) available
                    ORDER BY priority DESC, next_attempt_at, media_id LIMIT %s
                )
                UPDATE media_ingestion_job j SET state = 'running', lease_token = %s::uuid,
                    lease_until = now() + %s, attempts = attempts + 1, updated_at = now()
                FROM candidates c WHERE j.media_id = c.media_id
                RETURNING j.media_id, j.attempts
            ''', (limit, limit, limit, str(token), timedelta(seconds=lease_seconds)))
            return cursor.fetchall()

    def renew(self, token: UUID, *, lease_seconds: float = 120) -> None:
        with self.transaction() as cursor:
            cursor.execute('''UPDATE media_ingestion_job SET lease_until = now() + %s, updated_at = now()
                WHERE state = 'running' AND lease_token = %s::uuid''',
                           (timedelta(seconds=lease_seconds), str(token)))

    def release(self, token: UUID) -> None:
        with self.transaction() as cursor:
            cursor.execute('''UPDATE media_ingestion_job SET state = 'pending', lease_token = NULL,
                lease_until = NULL, attempts = GREATEST(0, attempts - 1), updated_at = now()
                WHERE state = 'running' AND lease_token = %s::uuid''', (str(token),))

    def fail(self, token: UUID, movie_id: int, *, error: str, delay: float, terminal: bool) -> None:
        with self.transaction() as cursor:
            cursor.execute('''UPDATE media_ingestion_job SET state = %s, lease_token = NULL,
                lease_until = NULL, next_attempt_at = now() + %s, last_error = %s, updated_at = now()
                WHERE media_id = %s AND state = 'running' AND lease_token = %s::uuid''',
                           ('failed' if terminal else 'pending', timedelta(seconds=delay),
                            error[:2000], movie_id, str(token)))

    def existing_media_ids(self, movie_ids: list[int]) -> set[int]:
        if not movie_ids:
            return set()
        with self.transaction() as cursor:
            cursor.execute('SELECT media_id FROM media WHERE media_id = ANY(%s)', (movie_ids,))
            return {row[0] for row in cursor.fetchall()}

    def save(self, movies: list[Movie | MovieDetails], token: UUID, *, refresh_days: float = 14,
             min_votes: int | None = None) -> int:
        if min_votes is not None and (type(min_votes) is not int or min_votes < 0):
            raise ValueError('min_votes must be a nonnegative integer')
        records = {item.id: item if isinstance(item, MovieDetails) else MovieDetails(movie=item) for item in movies}
        if not records:
            return 0
        with self.transaction() as cursor:
            cursor.execute('''SELECT media_id FROM media_ingestion_job WHERE media_id = ANY(%s)
                AND state = 'running' AND lease_token = %s::uuid AND lease_until > now()
                ORDER BY media_id FOR UPDATE''', (list(records), str(token)))
            owned_ids = [row[0] for row in cursor.fetchall()]
            skipped = []
            if min_votes is None:
                selected = [records[movie_id] for movie_id in owned_ids]
            else:
                cursor.execute('SELECT media_id FROM media WHERE media_id = ANY(%s) FOR KEY SHARE', (owned_ids,))
                existing = {row[0] for row in cursor.fetchall()}
                selected = []
                for movie_id in owned_ids:
                    detail = records[movie_id]
                    if movie_id in existing or votes_above(detail.movie, min_votes):
                        selected.append(detail)
                    else:
                        skipped.append(detail)
            changes = save_cards(cursor, selected)
            saved_ids = [detail.id for detail in selected]
            cursor.execute('''UPDATE media_ingestion_job SET state = 'pending', attempts = 0,
                lease_token = NULL, lease_until = NULL, last_error = NULL,
                last_success_at = CASE WHEN media_id = ANY(%s) THEN now() ELSE last_success_at END,
                next_attempt_at = now() + %s, updated_at = now()
                WHERE media_id = ANY(%s) AND lease_token = %s::uuid''',
                           (saved_ids, timedelta(days=refresh_days), owned_ids, str(token)))
        changes.log(selected, log_unchanged=self.log_unchanged)
        for detail in skipped:
            logger.info('[SKIP] media_id=%s title=%r votes=%s required=>%s',
                        detail.id, detail.movie.title, _vote_count(detail.movie), min_votes)
        return len(selected)

    def status(self) -> list[tuple]:
        with self.transaction() as cursor:
            cursor.execute('''SELECT state, count(*), count(*) FILTER (WHERE next_attempt_at <= now())
                FROM media_ingestion_job GROUP BY state ORDER BY state''')
            return cursor.fetchall()
