from collections import defaultdict

from psycopg2.extras import Json, execute_values

from db.ingestion.bulk import upsert_rows
from db.ingestion.details import DetailChanges, save_bot_sections, save_relationships, save_series
from db.ingestion.ratings import normalize_age_rating, normalize_mpaa_rating
from parser.graphql.models import Movie, MovieDetails


_ROLE_NAMES = {
    'actors': 'актеры', 'directors': 'режиссеры', 'writers': 'сценаристы',
    'producers': 'продюсеры', 'operators': 'операторы', 'composers': 'композиторы',
    'designers': 'художники', 'filmEditors': 'монтажеры',
}


def media_patch(movie: Movie) -> dict:
    # Film/TvSeries cannot distinguish animation; an original title need not be English.
    patch = movie.to_patch()
    row = {'media_id': movie.id, 'title': movie.title}
    for source, column in (
        ('description', 'description'), ('short_description', 'short_description'),
        ('slogan', 'slogan'), ('release_year', 'release_year'),
        ('duration_minutes', 'duration'),
        ('content_id', 'content_id'), ('top250', 'top250'), ('top10', 'top10'),
        ('votes_kp', 'votes'), ('votes_imdb', 'votes_imdb'),
    ):
        if source in patch:
            row[column] = patch[source]
    if 'rating_kp' in patch and (movie.rating_kp is None or 'value' in movie.rating_kp.model_fields_set):
        row['rating'] = movie.rating_kp.value if movie.rating_kp else None
    if 'votes_kp' not in patch and movie.rating_kp is not None and 'votes' in movie.rating_kp.model_fields_set:
        row['votes'] = movie.rating_kp.votes
    if 'rating_imdb' in patch and (movie.rating_imdb is None or 'value' in movie.rating_imdb.model_fields_set):
        row['rating_imdb'] = movie.rating_imdb.value if movie.rating_imdb else None
    if 'trailer_url' in patch:
        row['trailer'] = Json([{'url': movie.trailer_url}]) if movie.trailer_url else None
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


def save_cards(cursor, details: list[MovieDetails]) -> DetailChanges:
    changes = DetailChanges()
    movies = [detail.movie for detail in details]
    rows = [media_patch(movie) for movie in movies]
    for movie_id, action in upsert_rows(cursor, 'media', rows, 'media_id').items():
        changes.touch(movie_id, 'media')
        if action == 'INSERT':
            changes.inserted_media.add(movie_id)

    aliases = sorted({(movie.id, name) for movie in movies
                      for name in (movie.original_title, movie.russian_title) if name and name != movie.title})
    if aliases:
        inserted = execute_values(cursor, '''INSERT INTO media_alias(media_id,name) VALUES %s
            ON CONFLICT DO NOTHING RETURNING media_id''', aliases, fetch=True)
        for (movie_id,) in inserted:
            changes.touch(movie_id, 'media_alias')
    for table, field in (('genre', 'genres'), ('country', 'countries')):
        for movie_id in _save_entities(cursor, movies, table, field):
            changes.touch(movie_id, 'media_' + table)
    for movie_id, tables in _save_credits(cursor, movies).items():
        changes.tables.setdefault(movie_id, set()).update(tables)
    save_series(cursor, details, changes)
    save_relationships(cursor, details, changes)
    save_bot_sections(cursor, details, changes)
    return changes


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
