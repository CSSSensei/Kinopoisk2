import json
import os
from typing import Dict, List, Set, Tuple
from collections import defaultdict

from dotenv import find_dotenv, load_dotenv

from query_loader import load_query
import psycopg2
from psycopg2.extras import execute_batch

from api_get_movie import get_film

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


class DatabaseManager:
    def __init__(self):
        self.connection_params = {
            "dbname": os.getenv("DB_NAME"),
            "user": os.getenv("USER"),
            "password": os.getenv("PASSWORD"),
            "host": os.getenv("HOST"),
            "port": os.getenv("PORT"),
        }
        self.connection = None
        self.existing_media_ids = set()
        self.existing_genres = {}
        self.existing_countries = {}
        self.existing_roles = {}
        self.existing_persons = set()

    def get_connection(self):
        if self.connection is None or self.connection.closed:
            self.connection = psycopg2.connect(**self.connection_params)
        return self.connection

    def close_connection(self):
        if self.connection and not self.connection.closed:
            self.connection.close()
            self.connection = None

    def fetch_existing_data(self):
        conn = self.get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT media_id FROM media")
            self.existing_media_ids = {row[0] for row in cur.fetchall()}

            cur.execute("SELECT genre_id, name FROM genre")
            self.existing_genres = {row[1]: row[0] for row in cur.fetchall()}

            cur.execute("SELECT country_id, name FROM country")
            self.existing_countries = {row[1]: row[0] for row in cur.fetchall()}

            cur.execute("SELECT role_id, name FROM role")
            self.existing_roles = {row[1]: row[0] for row in cur.fetchall()}

            cur.execute("SELECT person_id FROM person")
            self.existing_persons = {row[0] for row in cur.fetchall()}

    def insert_genres_batch(self, genre_names: Set[str]):
        if not genre_names:
            return

        conn = self.get_connection()
        new_genres = [name for name in genre_names if name not in self.existing_genres]

        if not new_genres:
            return

        try:
            with conn.cursor() as cur:
                genre_data = [(name,) for name in new_genres]
                execute_batch(cur, SQL_GENRE, genre_data)

                for name in new_genres:
                    cur.execute("SELECT genre_id FROM genre WHERE name = %s", (name,))
                    result = cur.fetchone()
                    if result:
                        genre_id = result[0]
                        self.existing_genres[name] = genre_id

                conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"Error inserting genres: {e}")

    def insert_countries_batch(self, country_names: Set[str]):
        """Insert countries in batch"""
        if not country_names:
            return

        conn = self.get_connection()
        new_countries = [
            name for name in country_names if name not in self.existing_countries
        ]

        if not new_countries:
            return

        try:
            with conn.cursor() as cur:
                country_data = [(name,) for name in new_countries]
                execute_batch(cur, SQL_COUNTRY, country_data)

                for name in new_countries:
                    cur.execute(
                        "SELECT country_id FROM country WHERE name = %s", (name,)
                    )
                    result = cur.fetchone()
                    if result:
                        country_id = result[0]
                        self.existing_countries[name] = country_id

                conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"Error inserting countries: {e}")

    def insert_roles_batch(self, role_names: Set[str]):
        """Insert roles in batch"""
        if not role_names:
            return

        conn = self.get_connection()
        new_roles = [name for name in role_names if name not in self.existing_roles]

        if not new_roles:
            return

        try:
            with conn.cursor() as cur:
                role_data = [(name,) for name in new_roles]
                execute_batch(cur, SQL_ROLE, role_data)

                for name in new_roles:
                    cur.execute("SELECT role_id FROM role WHERE name = %s", (name,))
                    result = cur.fetchone()
                    if result:
                        role_id = result[0]
                        self.existing_roles[name] = role_id

                conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"Error inserting roles: {e}")

    def insert_persons_batch(self, person_data: List[Tuple]):
        """Insert persons in batch"""
        if not person_data:
            return

        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                for person_row in person_data:
                    person_id = person_row[0]
                    if person_id not in self.existing_persons:
                        try:
                            cur.execute(SQL_PERSON, person_row)
                            self.existing_persons.add(person_id)
                        except psycopg2.errors.UniqueViolation:
                            conn.rollback()
                            self.existing_persons.add(person_id)
                            continue

                conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"Error inserting persons: {e}")

    def save_movies_batch(self, movies: List[Dict]) -> int:
        if not movies:
            return 0

        all_genre_names = set()
        all_country_names = set()
        all_role_names = set()
        all_person_data = []
        movies_to_insert = []

        for movie in movies:
            if not movie.get("name") or not movie.get("rating", {}).get("kp"):
                continue

            movie_id = movie.get("id")
            if movie_id in self.existing_media_ids:
                continue

            genres = movie.get("genres", [])
            for g in genres:
                all_genre_names.add(g["name"])

            countries = movie.get("countries", [])
            for c in countries:
                all_country_names.add(c["name"])

            persons = movie.get("persons", [])
            persons = persons[:20] if persons else []
            for p in persons:
                person_id = p["id"]
                if not person_id:
                    continue
                person_ru_name = p["name"]
                person_en_name = p["enName"]
                person_photo_url = p["photo"]
                role = p["profession"]

                person_row = (
                    person_id,
                    person_ru_name,
                    person_en_name,
                    person_photo_url,
                    None,
                )
                all_person_data.append(person_row)

                if role:
                    all_role_names.add(role)

            movies_to_insert.append(movie)

        if not movies_to_insert:
            return 0

        self.insert_genres_batch(all_genre_names)
        self.insert_countries_batch(all_country_names)
        self.insert_roles_batch(all_role_names)
        self.insert_persons_batch(all_person_data)

        conn = self.get_connection()
        added_count = 0

        try:
            with conn.cursor() as cur:
                inserted_movies = []
                for movie in movies_to_insert:
                    movie_id = movie.get("id")
                    try:
                        cur.execute(
                            "SELECT media_id FROM media WHERE media_id = %s",
                            (movie_id,),
                        )
                        if cur.fetchone():
                            self.existing_media_ids.add(movie_id)
                            continue
                    except:
                        pass

                    movie_type = movie.get("type")
                    if movie_type == "tv-series":
                        movie_type = "series"
                    if movie_type not in {
                        "movie",
                        "series",
                        "cartoon",
                        "anime",
                        "animated-series",
                    }:
                        movie_type = "other"

                    try:
                        cur.execute(
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
                                json.dumps(movie.get("videos", {}).get("trailers")),
                                movie_type,
                            ),
                        )
                        result = cur.fetchone()
                        if result:
                            inserted_media_id = result[0]
                            inserted_movies.append((movie, inserted_media_id))
                            self.existing_media_ids.add(movie_id)
                    except psycopg2.errors.UniqueViolation:
                        conn.rollback()
                        self.existing_media_ids.add(movie_id)
                        continue

                media_genre_data = []
                media_country_data = []
                media_role_data = []

                for movie, media_id in inserted_movies:
                    genres = movie.get("genres", [])
                    for g in genres:
                        genre_name = g["name"]
                        if genre_name in self.existing_genres:
                            genre_id = self.existing_genres[genre_name]
                            media_genre_data.append((media_id, genre_id))

                    countries = movie.get("countries", [])
                    for c in countries:
                        country_name = c["name"]
                        if country_name in self.existing_countries:
                            country_id = self.existing_countries[country_name]
                            media_country_data.append((media_id, country_id))

                    persons = movie.get("persons", [])
                    persons = persons[:20] if persons else []
                    for p in persons:
                        person_id = p["id"]
                        if not person_id:
                            continue
                        role = p["profession"]
                        description = p["description"]

                        if (
                            person_id in self.existing_persons
                            and role in self.existing_roles
                        ):
                            role_id = self.existing_roles[role]
                            media_role_data.append(
                                (media_id, person_id, role_id, description)
                            )

                if media_genre_data:
                    execute_batch(cur, SQL_MEDIA_GENRE, media_genre_data)

                if media_country_data:
                    execute_batch(cur, SQL_MEDIA_COUNTRY, media_country_data)

                if media_role_data:
                    execute_batch(cur, SQL_MEDIA_ROLE, media_role_data)

                conn.commit()
                added_count = len(inserted_movies)
                for movie, _ in inserted_movies:
                    print(f"Добавлен фильм: {movie.get('name')}")

        except Exception as e:
            conn.rollback()
            print(f"Ошибка при добавлении фильмов: {e}")
            added_count = 0

        return added_count


def add_movies(page_start: int, page_end: int, batch_size: int = 50):
    if page_start > page_end:
        print("page_end должен быть больше page_start")
        return

    db_manager = DatabaseManager()
    try:
        print("Загрузка существующих данных...")
        db_manager.fetch_existing_data()

        cnt = 0
        batch = []

        for i in range(page_start, page_end):
            movies = get_film(i)
            for movie in movies:
                batch.append(movie)

                if len(batch) >= batch_size:
                    added = db_manager.save_movies_batch(batch)
                    cnt += added
                    batch = []
                    print(f"Обработано {cnt} фильмов")

        if batch:
            added = db_manager.save_movies_batch(batch)
            cnt += added

        print(f"Всего добавлено {cnt} фильмов")

    finally:
        db_manager.close_connection()


if __name__ == "__main__":
    add_movies(59, 300, batch_size=250)
