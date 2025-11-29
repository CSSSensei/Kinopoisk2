import json
import os

from dotenv import find_dotenv, load_dotenv

from query_loader import load_query
import psycopg2

from api_get_movie import get_film

SQL_CREATE_TABLES = load_query("create_tables.sql")
SQL_MEDIA = load_query("media/add_media.sql")
SQL_GENRE = load_query("media/add_genre.sql")
SQL_COUNTRY = load_query("media/add_country.sql")
SQL_MEDIA_GENRE = load_query("media/add_media_genre.sql")
SQL_MEDIA_COUNTRY = load_query("media/add_media_country.sql")
SQL_PERSON = load_query("person/add_person.sql")
SQL_ROLE = load_query("role/add_role.sql")
SQL_MEDIA_ROLE = load_query("person/add_media_person_role.sql")
SQL_SEQUELS = load_query("media/add_connected_media.sql")

load_dotenv(find_dotenv())


def get_connection():
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("USER"),
        password=os.getenv("PASSWORD"),
        host=os.getenv("HOST"),
        port=os.getenv("PORT"),
    )


def select_fetch_all(query: str, params: tuple):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            result = cur.fetchall()
            return result


def execute_returning(query: str, params: tuple):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            conn.commit()
            result = cur.fetchone()
            if not result:
                return None
            return result[0]


def execute_no_return(query: str, params: tuple):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            conn.commit()


def save_movie(movie: dict) -> int:
    if not movie.get("name") or not movie.get("rating", {}).get("kp"):
        return 0
    movie_id = movie.get("id")
    if execute_returning("SELECT title FROM media WHERE media_id=%s", (movie_id,)):
        return 0
    movie_type = movie.get("type")
    match movie_type:
        case "tv-series":
            movie_type = "series"
    if movie_type not in {"movie", "series", "cartoon", "anime", "animated-series"}:
        movie_type = "other"
    media_id = execute_returning(
        SQL_MEDIA,
        (
            movie_id,
            movie.get("externalId", {}).get("imdb"),
            movie.get("name"),
            movie.get("rating", {}).get("kp"),
            movie.get("votes", {}).get("kp"),
            movie.get("enName"),
            movie.get("description"),
            movie.get("shortDescription"),
            movie.get("slogan"),
            movie.get("year"),
            movie.get("movieLength"),
            movie.get("poster", {}).get("url"),
            movie.get("poster", {}).get("previewUrl"),
            movie.get("logo", {}).get("url"),
            movie.get("ageRating"),
            movie.get("ratingMpaa"),
            json.dumps(movie.get("budget")),
            json.dumps(movie.get("fees")),
            movie.get("trailers"),
            movie_type,
        ),
    )

    genres = movie.get("genres", [])
    for g in genres:
        genre_name = g["name"]
        try:
            genre_id = execute_returning(SQL_GENRE, (genre_name,))
        except psycopg2.errors.UniqueViolation:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT genre_id FROM genre WHERE name=%s", (genre_name,)
                    )
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
                    cur.execute(
                        "SELECT country_id FROM country WHERE name=%s", (country_name,)
                    )
                    country_id = cur.fetchone()[0]

        execute_no_return(SQL_MEDIA_COUNTRY, (media_id, country_id))
    persons = movie.get("persons", [])
    persons = persons[:20] if persons else []
    for p in persons:
        person_id = p["id"]
        person_ru_name = p["name"]
        person_en_name = p["enName"]
        person_photo_url = p["photo"]
        role = p["profession"]
        description = p["description"]
        try:
            execute_no_return(
                SQL_PERSON,
                (person_id, person_ru_name, person_en_name, person_photo_url, None),
            )
        except psycopg2.errors.UniqueViolation:
            pass
        try:
            role_id = execute_returning(SQL_ROLE, (role,))
        except psycopg2.errors.UniqueViolation:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT role_id FROM role WHERE name=%s", (role,))
                    role_id = cur.fetchone()[0]

        execute_no_return(SQL_MEDIA_ROLE, (media_id, person_id, role_id, description))

    print(f"Добавлен фильм: {movie.get('name')}")
    return 1


def add_movies(page_start: int, page_end: int):
    cnt = 0
    if page_start > page_end:
        print("page_end должен быть больше page_start")
        return
    for i in range(page_start, page_end):
        for movie in get_film(i):
            cnt += save_movie(movie)

    print(f"Добавлено {cnt} фильмов")


if __name__ == "__main__":
    # execute_no_return(SQL_CREATE_TABLES, tuple())
    add_movies(4, 9)
