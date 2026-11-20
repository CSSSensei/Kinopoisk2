import logging
from collections import Counter
from dataclasses import dataclass, field

from psycopg2 import sql
from psycopg2.extras import execute_values

from db.ingestion.bulk import upsert_rows
from parser.graphql.models import MovieDetails


logger = logging.getLogger(__name__)
_GENERIC_RELATION = 'Связанный фильм'
_RELATION_NAMES = {'BEFORE': 'Начало', 'AFTER': 'Продолжение', 'REMAKE': 'Ремейк'}


@dataclass
class DetailChanges:
    inserted_media: set[int] = field(default_factory=set)
    tables: dict[int, set[str]] = field(default_factory=dict)
    seasons: dict[tuple[int, int], str] = field(default_factory=dict)
    episodes: dict[tuple[int, int, int], str] = field(default_factory=dict)
    links: list[tuple[str, int, int, str]] = field(default_factory=list)
    deferred: dict[int, int] = field(default_factory=dict)
    queued: int = 0

    def touch(self, movie_id: int, table: str):
        self.tables.setdefault(movie_id, set()).add(table)

    def log(self, details: list[MovieDetails], *, log_unchanged: bool):
        counts = Counter()
        for detail in details:
            tables = self.tables.get(detail.id, ())
            action = 'UPDATE' if tables else 'UNCHANGED'
            if detail.id in self.inserted_media:
                action = 'INSERT'
            counts[action] += 1
            if tables or log_unchanged:
                logger.info('[%s] media_id=%s title=%r tables=%s', action, detail.id,
                            detail.movie.title, ','.join(sorted(tables)) or '-')
        logger.info('Committed: inserted=%s updated=%s unchanged=%s',
                    counts['INSERT'], counts['UPDATE'], counts['UNCHANGED'])

        for (movie_id, number), action in sorted(self.seasons.items()):
            logger.info('[SEASON %s] media_id=%s season=%s', action, movie_id, number)
        for (movie_id, season, episode), action in sorted(self.episodes.items()):
            logger.info('[EPISODE %s] media_id=%s season=%s episode=%s', action, movie_id, season, episode)
        for action, movie_id, target, name in self.links:
            logger.info('[LINK %s] media_id=%s related_media_id=%s type=%r', action, movie_id, target, name)
        for movie_id, count in sorted(self.deferred.items()):
            logger.info('[DEFERRED] media_id=%s relationships=%s waiting for related cards', movie_id, count)
        if self.queued:
            logger.info('Queued related cards: %s', self.queued)
        for detail in details:
            episodes = detail.episodes
            if episodes is not None:
                season_numbers = {season.number for season in detail.seasons}
                season_numbers.update(episode.season_number for episode in episodes.items)
                if detail.movie.seasons_count is not None and len(season_numbers) < detail.movie.seasons_count:
                    logger.warning('[PARTIAL SEASONS] media_id=%s fetched=%s total=%s',
                                   detail.id, len(season_numbers), detail.movie.seasons_count)
                logger.info('[EPISODES] media_id=%s fetched=%s total=%s complete=%s',
                            detail.id, episodes.fetched, episodes.total, episodes.complete)
                if not episodes.complete:
                    logger.warning('[PARTIAL EPISODES] media_id=%s %s', detail.id, '; '.join(episodes.limitations))
            relationships = detail.relationships
            if relationships is not None and relationships.items and not relationships.complete:
                logger.warning('[PARTIAL RELATIONSHIPS] media_id=%s %s',
                               detail.id, '; '.join(relationships.limitations))


def save_series(cursor, details: list[MovieDetails], changes: DetailChanges):
    seasons = {(detail.id, season.number) for detail in details for season in detail.seasons}
    episodes = [episode for detail in details if detail.episodes is not None for episode in detail.episodes.items]
    seasons.update((episode.movie_id, episode.season_number) for episode in episodes)
    if not seasons:
        return
    rows = [{'media_id': movie_id, 'season_number': number} for movie_id, number in sorted(seasons)]
    changes.seasons.update(upsert_rows(cursor, 'season', rows, ('media_id', 'season_number')))
    for movie_id, _ in changes.seasons:
        changes.touch(movie_id, 'season')
    cursor.execute('SELECT season_id, media_id, season_number FROM season WHERE media_id = ANY(%s)',
                   (sorted({movie_id for movie_id, _ in seasons}),))
    mapping = {(movie_id, number): season_id for season_id, movie_id, number in cursor.fetchall()}
    rows = []
    for episode in episodes:
        # API episode IDs and local SERIAL episode_id belong to different namespaces.
        row = {'season_id': mapping[(episode.movie_id, episode.season_number)], 'episode_number': episode.episode_number}
        for field_name in ('title', 'description'):
            if field_name in episode.loaded_fields:
                row[field_name] = getattr(episode, field_name)
        if 'release_date' in episode.loaded_fields:
            if episode.release_date is None:
                row['release_date'] = None
            elif episode.release_date.exact_date is not None:
                row['release_date'] = episode.release_date.exact_date.isoformat()
        rows.append(row)
    saved = upsert_rows(cursor, 'episode', rows, ('season_id', 'episode_number'))
    reverse = {season_id: slot for slot, season_id in mapping.items()}
    for (season_id, number), action in saved.items():
        movie_id, season_number = reverse[season_id]
        changes.episodes[(movie_id, season_number, number)] = action
        changes.touch(movie_id, 'episode')


def save_bot_sections(cursor, details: list[MovieDetails], changes: DetailChanges):
    facts = []
    fact_counts = []
    recommendations = []
    complete_lists = []
    for detail in details:
        if detail.facts is not None:
            facts.extend(dict(media_id=detail.id, position=position, body=fact.text, is_spoiler=fact.is_spoiler)
                         for position, fact in enumerate(detail.facts, 1))
            fact_counts.append((detail.id, len(detail.facts)))
        if detail.similar is not None:
            recommendations.extend(dict(media_id=detail.id, recommended_id=target, position=position)
                                   for position, target in enumerate(detail.similar.items, 1))
            if detail.similar.complete:
                complete_lists.append((detail.id, list(detail.similar.items)))
    for table, rows, key in (("media_fact", facts, "position"),
                              ("media_recommendation", recommendations, "recommended_id")):
        for media_id, _ in upsert_rows(cursor, table, rows, ("media_id", key)):
            changes.touch(media_id, table)
    if fact_counts:
        removed = execute_values(cursor, """DELETE FROM media_fact f USING (VALUES %s) AS snapshot(id, count)
            WHERE f.media_id=snapshot.id AND f.position>snapshot.count RETURNING media_id""", fact_counts, fetch=True)
        for (media_id,) in removed:
            changes.touch(media_id, "media_fact")
    if complete_lists:
        removed = execute_values(cursor, """DELETE FROM media_recommendation r USING (VALUES %s) AS snapshot(id, targets)
            WHERE r.media_id=snapshot.id AND NOT (r.recommended_id=ANY(snapshot.targets::integer[]))
            RETURNING media_id""", complete_lists, fetch=True)
        for (media_id,) in removed:
            changes.touch(media_id, "media_recommendation")


def save_relationships(cursor, details: list[MovieDetails], changes: DetailChanges):
    items = [item for detail in details if detail.relationships is not None for item in detail.relationships.items]
    if items:
        names = sorted({_RELATION_NAMES.get(item.relationship_type, _GENERIC_RELATION) for item in items})
        execute_values(cursor, 'INSERT INTO connection_type(name) VALUES %s ON CONFLICT(name) DO NOTHING',
                       [(name,) for name in names])
        cursor.execute('SELECT connection_type_id, name FROM connection_type WHERE name = ANY(%s)', (names,))
        mapping = {name: key for key, name in cursor.fetchall()}
        rows = sorted({(item.movie_id, item.related_movie_id,
                        mapping[_RELATION_NAMES.get(item.relationship_type, _GENERIC_RELATION)],
                        item.relationship_type not in _RELATION_NAMES) for item in items})
        inserted = execute_values(cursor, '''INSERT INTO media_ingestion_relation
            (media_id, related_media_id, connection_id)
            SELECT item.media_id,item.related_media_id,item.connection_id
            FROM (VALUES %s) AS item(media_id,related_media_id,connection_id,is_generic)
            WHERE NOT EXISTS(SELECT 1 FROM connected_media existing
                WHERE existing.media_id = item.media_id AND existing.parent_id = item.related_media_id
                    AND (existing.connection_id = item.connection_id OR item.is_generic))
            ON CONFLICT DO NOTHING RETURNING media_id''',
                                  rows, page_size=1000, fetch=True)
        for row in inserted:
            changes.touch(row[0], 'media_ingestion_relation')
    ids = [detail.id for detail in details]
    if not ids:
        return
    cursor.execute('''INSERT INTO media_ingestion_job(media_id, source, priority)
        SELECT DISTINCT p.related_media_id, 'relationship', 10 FROM media_ingestion_relation p
        WHERE p.media_id = ANY(%s) AND NOT EXISTS(SELECT 1 FROM media m WHERE m.media_id = p.related_media_id)
        ON CONFLICT(media_id) DO NOTHING''', (ids,))
    changes.queued = cursor.rowcount
    _resolve_relationships(cursor, ids, changes)
    cursor.execute('''SELECT media_id, count(*) FROM media_ingestion_relation
        WHERE media_id = ANY(%s) GROUP BY media_id''', (ids,))
    changes.deferred.update(cursor.fetchall())


def _resolve_relationships(cursor, ids: list[int], changes: DetailChanges):
    cursor.execute('''SELECT p.media_id, p.related_media_id, p.connection_id, t.name
        FROM media_ingestion_relation p
        JOIN media target ON target.media_id = p.related_media_id
        JOIN connection_type t ON t.connection_type_id = p.connection_id
        WHERE p.media_id = ANY(%s) OR p.related_media_id = ANY(%s)
        ORDER BY p.media_id, p.related_media_id, p.connection_id FOR UPDATE OF p''', (ids, ids))
    ready = cursor.fetchall()
    if not ready:
        return
    typed = [row[:3] for row in ready if row[3] != _GENERIC_RELATION]
    generic = [row[:3] for row in ready if row[3] == _GENERIC_RELATION]
    names = {row[2]: row[3] for row in ready}
    inserted = []
    if typed:
        inserted.extend(execute_values(cursor, '''INSERT INTO connected_media(media_id,parent_id,connection_id)
            VALUES %s ON CONFLICT DO NOTHING RETURNING media_id,parent_id,connection_id''',
                                       typed, page_size=1000, fetch=True))
        statement = sql.SQL('''DELETE FROM connected_media old USING (VALUES %s) AS known(media_id,parent_id,connection_id),
            connection_type t WHERE old.media_id = known.media_id AND old.parent_id = known.parent_id
                AND old.connection_id = t.connection_type_id AND t.name = {}
            RETURNING old.media_id,old.parent_id''').format(sql.Literal(_GENERIC_RELATION))
        removed = execute_values(cursor, statement.as_string(cursor), typed, page_size=1000, fetch=True)
        for movie_id, target in removed:
            changes.links.append(('DELETE', movie_id, target, _GENERIC_RELATION))
            changes.touch(movie_id, 'connected_media')
    if generic:
        inserted.extend(execute_values(cursor, '''INSERT INTO connected_media(media_id,parent_id,connection_id)
            SELECT item.media_id,item.parent_id,item.connection_id
            FROM (VALUES %s) AS item(media_id,parent_id,connection_id)
            WHERE NOT EXISTS(SELECT 1 FROM connected_media existing
                WHERE existing.media_id = item.media_id AND existing.parent_id = item.parent_id)
            ON CONFLICT DO NOTHING RETURNING media_id,parent_id,connection_id''',
                                       generic, page_size=1000, fetch=True))
    for movie_id, target, connection_id in inserted:
        changes.links.append(('INSERT', movie_id, target, names[connection_id]))
        changes.touch(movie_id, 'connected_media')
    execute_values(cursor, '''DELETE FROM media_ingestion_relation pending
        USING (VALUES %s) AS resolved(media_id,related_media_id,connection_id)
        WHERE pending.media_id = resolved.media_id AND pending.related_media_id = resolved.related_media_id
            AND pending.connection_id = resolved.connection_id''', [row[:3] for row in ready], page_size=1000)
