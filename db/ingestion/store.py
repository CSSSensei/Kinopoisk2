import logging
from collections import defaultdict
from contextlib import contextmanager
from datetime import timedelta
from io import StringIO
from uuid import UUID

from psycopg2.extras import Json, execute_values

from db.ingestion.bulk import upsert_rows
from db.ingestion.details import DetailChanges, save_relationships, save_series
from db.ingestion.ratings import normalize_age_rating, normalize_mpaa_rating
from parser.graphql.models import Movie, MovieDetails


_ROLE_NAMES = {
    'actors': 'актеры', 'directors': 'режиссеры', 'writers': 'сценаристы',
    'producers': 'продюсеры', 'operators': 'операторы', 'composers': 'композиторы',
    'designers': 'художники', 'filmEditors': 'монтажеры',
}
_WORKER_LOCK = 723049381
logger = logging.getLogger(__name__)


def votes_above(movie: Movie, threshold: int) -> bool:
    rating = movie.rating_kp
    return rating is not None and rating.votes is not None and rating.votes > threshold


def media_patch(movie: Movie) -> dict:
    # Film/TvSeries cannot distinguish animation; an original title need not be English.
    patch = movie.to_patch()
    row = {'media_id': movie.id, 'title': movie.title}
    for source, column in (
        ('description', 'description'), ('short_description', 'short_description'),
        ('slogan', 'slogan'), ('release_year', 'release_year'),
        ('duration_minutes', 'duration'),
    ):
        if source in patch:
            row[column] = patch[source]
    if 'rating_kp' in patch:
        row['rating'] = movie.rating_kp.value if movie.rating_kp else None
        row['votes'] = movie.rating_kp.votes if movie.rating_kp else None
    for source, column in (('budget', 'budget_value'), ('fees_world', 'fees_world')):
        if source in patch:
            row[column] = Json(patch[source]) if patch[source] is not None else None
    if 'age_rating' in patch:
        row['age_rating'] = normalize_age_rating(movie.age_rating)
    if 'rating_mpaa' in patch:
        row['rating_mpaa'] = normalize_mpaa_rating(movie.rating_mpaa)
    if 'poster' in patch and (movie.poster is None or movie.poster.fallback_url):
        row['posterurl'] = movie.poster.fallback_url if movie.poster else None
    return row



class IngestionStore:
    def __init__(self, engine, *, log_unchanged: bool = False):
        self.engine = engine
        self.log_unchanged = log_unchanged

    @contextmanager
    def transaction(self):
        connection = self.engine.raw_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL search_path = public, pg_catalog")
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
                WHERE n.nspname = 'public' AND i.indisunique AND i.indisvalid
                    AND i.indimmediate AND i.indpred IS NULL AND i.indexprs IS NULL
                    AND k.ordinality <= i.indnkeyatts
                GROUP BY c.relname, i.indexrelid
            ''')
            found = {(table, frozenset(columns)) for table, columns in cursor.fetchall()}
        missing = [f'{table}({", ".join(sorted(columns))})'
                   for table, columns in required.items() if (table, frozenset(columns)) not in found]
        if missing:
            raise RuntimeError('Missing unique keys: ' + ', '.join(missing)
                               + '. Check migrations V001, V004, V005 and V006; migrations are not applied automatically.')

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
        detail_changes = DetailChanges()
        with self.transaction() as cursor:
            cursor.execute('''SELECT media_id FROM media_ingestion_job WHERE media_id = ANY(%s)
                AND state = 'running' AND lease_token = %s::uuid AND lease_until > now()
                ORDER BY media_id FOR UPDATE''', (list(records), str(token)))
            owned_details = [records[row[0]] for row in cursor.fetchall()]
            skipped = []
            if min_votes is not None:
                cursor.execute('SELECT media_id FROM media WHERE media_id = ANY(%s) FOR KEY SHARE',
                               ([detail.id for detail in owned_details],))
                existing = {row[0] for row in cursor.fetchall()}
                skipped = [detail for detail in owned_details
                           if detail.id not in existing and not votes_above(detail.movie, min_votes)]
                skipped_ids = {detail.id for detail in skipped}
                owned_details = [detail for detail in owned_details if detail.id not in skipped_ids]
            owned = [detail.movie for detail in owned_details]
            changes = upsert_rows(cursor, 'media', [media_patch(movie) for movie in owned], 'media_id')
            touched = {movie.id: set() for movie in owned}
            for media_id in changes:
                touched[media_id].add('media')
            for table, field in (('genre', 'genres'), ('country', 'countries')):
                for media_id in self._save_entities(cursor, owned, table, field):
                    touched[media_id].add('media_' + table)
            for media_id, tables in self._save_credits(cursor, owned).items():
                touched[media_id].update(tables)
            save_series(cursor, owned_details, detail_changes)
            save_relationships(cursor, owned_details, detail_changes)
            for media_id, tables in detail_changes.tables.items():
                if media_id in touched:
                    touched[media_id].update(tables)
            ids = [movie.id for movie in owned]
            cursor.execute('''UPDATE media_ingestion_job SET state = 'pending', attempts = 0,
                lease_token = NULL, lease_until = NULL, last_error = NULL, last_success_at = now(),
                next_attempt_at = now() + %s, updated_at = now() WHERE media_id = ANY(%s)
                AND lease_token = %s::uuid''', (timedelta(days=refresh_days), ids, str(token)))
            if skipped:
                cursor.execute('''UPDATE media_ingestion_job SET state = 'pending', attempts = 0,
                    lease_token = NULL, lease_until = NULL, last_error = NULL,
                    next_attempt_at = now() + %s, updated_at = now() WHERE media_id = ANY(%s)
                    AND lease_token = %s::uuid''',
                               (timedelta(days=refresh_days), [detail.id for detail in skipped], str(token)))
        counts = defaultdict(int)
        for movie in owned:
            action = 'INSERT' if changes.get(movie.id) == 'INSERT' else 'UPDATE' if touched[movie.id] else 'UNCHANGED'
            counts[action] += 1
            if action != 'UNCHANGED' or self.log_unchanged:
                logger.info('[%s] media_id=%s title=%r tables=%s', action, movie.id, movie.title,
                            ','.join(sorted(touched[movie.id])) or '-')
        logger.info('Committed: inserted=%s updated=%s unchanged=%s',
                    counts['INSERT'], counts['UPDATE'], counts['UNCHANGED'])
        for detail in skipped:
            votes = detail.movie.rating_kp.votes if detail.movie.rating_kp else None
            logger.info('[SKIP] media_id=%s title=%r votes=%s required=>%s',
                        detail.id, detail.movie.title, votes, min_votes)
        detail_changes.log(owned_details)
        return len(owned)

    @staticmethod
    def _save_entities(cursor, movies: list[Movie], table: str, field: str) -> set[int]:
        selected = [movie for movie in movies if field in movie.loaded_fields]
        if not selected:
            return set()
        names = sorted({entity.name for movie in selected for entity in getattr(movie, field)})
        identifier = table + '_id'
        if names:
            execute_values(cursor, f'INSERT INTO {table} (name) VALUES %s ON CONFLICT (name) DO NOTHING',
                           [(name,) for name in names], page_size=1000)
            cursor.execute(f'SELECT {identifier}, name FROM {table} WHERE name = ANY(%s)', (names,))
            mapping = {name: key for key, name in cursor.fetchall()}
        else:
            mapping = {}
        # Kinopoisk dictionary IDs are not the local SERIAL keys.
        links = sorted({(movie.id, mapping[entity.name]) for movie in selected for entity in getattr(movie, field)})
        affected = set()
        if links:
            inserted = execute_values(cursor, f'''INSERT INTO media_{table} (media_id, {identifier}) VALUES %s
                ON CONFLICT DO NOTHING RETURNING media_id''', links, page_size=1000, fetch=True)
            affected.update(row[0] for row in inserted)
        deleted = execute_values(cursor, f'''DELETE FROM media_{table} existing
            USING (VALUES %s) AS snapshot(media_id, entity_ids)
            WHERE existing.media_id = snapshot.media_id
                AND NOT (existing.{identifier} = ANY(snapshot.entity_ids::integer[]))
            RETURNING existing.media_id''',
                       [(movie.id, sorted({mapping[entity.name] for entity in getattr(movie, field)}))
                        for movie in selected], page_size=1000, fetch=True)
        affected.update(row[0] for row in deleted)
        return affected

    @staticmethod
    def _save_credits(cursor, movies: list[Movie]) -> dict[int, set[str]]:
        roles = sorted({credit.role for movie in movies for credit in movie.credits})
        if not roles:
            return {}
        names = [_ROLE_NAMES[role] for role in roles]
        execute_values(cursor, 'INSERT INTO role (name) VALUES %s ON CONFLICT (name) DO NOTHING',
                       [(name,) for name in names])
        cursor.execute('SELECT role_id, name FROM role WHERE name = ANY(%s)', (names,))
        mapping = {name: key for key, name in cursor.fetchall()}
        people = {person.id: person for movie in movies for credit in movie.credits for person in credit.people}
        person_changes = upsert_rows(cursor, 'person', [{'person_id': person.id, 'ru_name': person.name} for person in people.values()], 'person_id')
        affected = defaultdict(set)
        for movie in movies:
            if any(person.id in person_changes for credit in movie.credits for person in credit.people):
                affected[movie.id].add('person')
        links = sorted({(movie.id, person.id, mapping[_ROLE_NAMES[credit.role]])
                        for movie in movies for credit in movie.credits for person in credit.people})
        if links:
            inserted = execute_values(cursor, '''INSERT INTO media_person_role (media_id, person_id, role_id)
                VALUES %s ON CONFLICT (media_id, person_id, role_id) DO NOTHING RETURNING media_id''',
                                      links, page_size=1000, fetch=True)
            for row in inserted:
                affected[row[0]].add('media_person_role')
        complete = [(movie.id, mapping[_ROLE_NAMES[credit.role]], sorted({person.id for person in credit.people}))
                    for movie in movies for credit in movie.credits if credit.complete is True]
        if complete:
            deleted = execute_values(cursor, '''DELETE FROM media_person_role existing
                USING (VALUES %s) AS snapshot(media_id, role_id, person_ids)
                WHERE existing.media_id = snapshot.media_id AND existing.role_id = snapshot.role_id
                    AND NOT (existing.person_id = ANY(snapshot.person_ids::integer[]))
                RETURNING existing.media_id''', complete, page_size=1000, fetch=True)
            for row in deleted:
                affected[row[0]].add('media_person_role')
        return affected

    def status(self) -> list[tuple]:
        with self.transaction() as cursor:
            cursor.execute('''SELECT state, count(*), count(*) FILTER (WHERE next_attempt_at <= now())
                FROM media_ingestion_job GROUP BY state ORDER BY state''')
            return cursor.fetchall()
