import json
import os

from DB.query_loader import load_query
import psycopg2

SQL_MEDIA = load_query("sql/media/add_media.sql")
SQL_GENRE = load_query("sql/media/add_genre.sql")
SQL_COUNTRY = load_query("sql/media/add_country.sql")
SQL_MEDIA_GENRE = load_query("sql/media/add_media_genre.sql")
SQL_MEDIA_COUNTRY = load_query("sql/media/add_media_country.sql")
SQL_PERSON = load_query("sql/person/add_person.sql")
SQL_ROLE = load_query("sql/role/add_role.sql")
SQL_MEDIA_ROLE = load_query("sql/person/add_media_person_role.sql")


def get_connection():
    return psycopg2.connect(
        dbname=os.getenv('DB_NAME'),
        user=os.getenv('USER'),
        password=os.getenv('PASSWORD'),
        host=os.getenv('HOST'),
        port=os.getenv('PORT'),
    )


def execute_returning(query: str, params: tuple):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            result = cur.fetchone()[0]
            conn.commit()
            return result


def execute_no_return(query: str, params: tuple):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            conn.commit()


def save_movie(movie: dict):
    media_id = execute_returning(
        SQL_MEDIA,
        (
            movie.get("id"),
            movie.get("name"),
            movie.get("name"),
            movie.get("enName"),
            movie.get("alternativeName"),
            movie.get("alternativeName"),
            movie.get("description"),
            movie.get("shortDescription"),
            movie.get("slogan"),  # slogan
            movie.get("year"),
            movie.get("movieLength"),
            movie.get("poster", {}).get("url"),
            movie.get("poster", {}).get("previewUrl"),
            movie.get("logo", {}).get("url"),
            movie.get("logo", {}).get("previewUrl"),
            movie.get("ageRating"),  # age_rating
            movie.get("ratingMpaa"),  # rating_mpaa
            json.dumps(movie.get("budget")),  # TODO budget_value
            movie.get("fees"),  # fees_world
            movie.get("type"),
        )
    )

    genres = movie.get("genres", [])
    for g in genres:
        genre_name = g["name"]
        try:
            genre_id = execute_returning(SQL_GENRE, (genre_name,))
        except psycopg2.errors.UniqueViolation:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT genre_id FROM genre WHERE name=%s", (genre_name,))
                    genre_id = cur.fetchone()[0]

        execute_no_return(SQL_MEDIA_GENRE, (media_id, genre_id))

    countries = movie.get("countries", [])
    for c in countries:
        country_name = c["name"]

        try:
            country_id = execute_returning(SQL_COUNTRY, (country_name,))
        except psycopg2.errors.UniqueViolation:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT country_id FROM country WHERE name=%s", (country_name,))
                    country_id = cur.fetchone()[0]

        execute_no_return(SQL_MEDIA_COUNTRY, (media_id, country_id))
    persons = movie.get("person", [])
    for p in persons:
        person_id = p["id"]
        person_ru_name = p["name"]
        person_en_name = p["enName"]
        person_photo_url = p["photo"]
        role = p["profession"]
        try:
            person_id = execute_returning(SQL_PERSON, (person_id, person_ru_name, person_en_name, person_photo_url, None))
        except psycopg2.errors.UniqueViolation:
            pass
        try:
            role_id = execute_returning(SQL_ROLE, (role,))
        except psycopg2.errors.UniqueViolation:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT role_id FROM role WHERE name=%s", (role,))
                    role_id = cur.fetchone()[0]

        execute_no_return(SQL_MEDIA_ROLE, (media_id, person_id, role_id))

    # TODO sequels
    print(f"✔ Movie saved: {movie.get('name')} (ID={media_id})")
