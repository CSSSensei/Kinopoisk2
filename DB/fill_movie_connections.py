import asyncio
import logging
import os
from typing import List, Dict, Set
import psycopg2
from psycopg2.extras import execute_batch

from dotenv import find_dotenv, load_dotenv

from parser.kinopoisk_parser import KinopoiskRelationshipParser, Relationship
from query_loader import load_query

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv(find_dotenv())

BATCH_SIZE = 50

SQL_GET_ALL_MEDIA_IDS = load_query("media/get_all_media_ids.sql")
SQL_GET_MEDIA_BY_ID = load_query("media/get_media_by_id.sql")
SQL_GET_OR_INSERT_CONNECTION_TYPE = load_query(
    "media/get_or_insert_connection_type.sql"
)
SQL_ADD_CONNECTED_MEDIA = load_query("media/add_connected_media.sql")


class DatabaseManager:
    def __init__(self):
        self.connection_params = {
            "dbname": os.getenv("DB_NAME"),
            "user": "a1142528_yan-toples",
            "password": os.getenv("PASSWORD"),
            "host": os.getenv("HOST"),
            "port": os.getenv("PORT"),
        }
        self.connection = None
        self.existing_connection_types = {}

    def get_connection(self):
        if self.connection is None or self.connection.closed:
            self.connection = psycopg2.connect(**self.connection_params)
        return self.connection

    def close_connection(self):
        if self.connection and not self.connection.closed:
            self.connection.close()
            self.connection = None

    def fetch_existing_connection_types(self):
        conn = self.get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT connection_id, type FROM sequels")
            self.existing_connection_types = {row[1]: row[0] for row in cur.fetchall()}

    def get_or_create_connection_type(self, relationship_type: str) -> int:
        if relationship_type in self.existing_connection_types:
            return self.existing_connection_types[relationship_type]

        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO sequels (type) VALUES (%s) ON CONFLICT (type) DO NOTHING",
                    (relationship_type,),
                )

                cur.execute(
                    "SELECT connection_id FROM sequels WHERE type = %s",
                    (relationship_type,),
                )
                result = cur.fetchone()
                conn.commit()

                if result:
                    connection_id = result[0]
                    self.existing_connection_types[relationship_type] = connection_id
                    return connection_id
                else:
                    raise Exception(
                        f"Ошибка получения type id связи для {relationship_type}"
                    )
        except Exception as e:
            conn.rollback()
            logger.error(
                f"Ошибка получения или создания типа связи {relationship_type}: {e}"
            )
            raise

    def get_all_movie_ids(self) -> List[int]:
        logger.info("Получаю все фильмы из БД...")
        conn = self.get_connection()
        with conn.cursor() as cur:
            cur.execute(SQL_GET_ALL_MEDIA_IDS)
            movie_ids = [row[0] for row in cur.fetchall()]
        logger.info(f"Найдено {len(movie_ids)} фильмов в БД")
        return movie_ids

    def media_exists(self, media_id: int) -> bool:
        conn = self.get_connection()
        with conn.cursor() as cur:
            cur.execute(SQL_GET_MEDIA_BY_ID, (media_id,))
            row = cur.fetchone()
            return row is not None

    def insert_connected_media_batch(self, connections: List[tuple]) -> None:
        if not connections:
            return

        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                execute_batch(cur, SQL_ADD_CONNECTED_MEDIA, connections)
                conn.commit()
                logger.info(f"Вставлено {len(connections)} связей")
        except Exception as e:
            conn.rollback()
            logger.error(f"Ошибка вставки связей: {e}")
            raise


def process_batch(db_manager: DatabaseManager, movie_ids: List[int]) -> None:
    logger.info(f"Обрабатываю батч из {len(movie_ids)} фильмов...")

    parser = KinopoiskRelationshipParser()

    relationships_batch = parser.get_all_relationships_batch(movie_ids)

    connections_to_insert = []

    for movie_id, relationships in relationships_batch.items():
        logger.info(f"Обрабатываю {len(relationships)} связей для фильма {movie_id}")

        for relationship in relationships:
            try:
                related_movie_id = int(relationship.related_movie_id)

                if related_movie_id == movie_id:
                    continue

                if not db_manager.media_exists(related_movie_id):
                    logger.debug(
                        f"Связанный фильм {related_movie_id} не найден в БД, скип"
                    )
                    continue

                connection_id = db_manager.get_or_create_connection_type(
                    relationship.relationship_type
                )

                connections_to_insert.append(
                    (movie_id, related_movie_id, connection_id)
                )
                logger.debug(
                    f"Добавлено отношение: {movie_id} -> {related_movie_id} ({relationship.relationship_type})"
                )

            except ValueError:
                logger.warning(f"Невалидный ID фильма: {relationship.related_movie_id}")
            except Exception as e:
                logger.error(f"Ошибка обработки отношения {relationship}: {e}")

    if connections_to_insert:
        db_manager.insert_connected_media_batch(connections_to_insert)


def main():
    logger.info("Пошла возня..")

    db_manager = DatabaseManager()

    try:
        db_manager.fetch_existing_connection_types()

        all_movie_ids = db_manager.get_all_movie_ids()

        for i in range(1100, len(all_movie_ids), BATCH_SIZE):
            batch = all_movie_ids[i : i + BATCH_SIZE]
            process_batch(db_manager, batch)

            progress = min(i + BATCH_SIZE, len(all_movie_ids))
            logger.info(f"Отработали {progress}/{len(all_movie_ids)} фильмов")

        logger.info("Дело сделано!")

    finally:
        db_manager.close_connection()


if __name__ == "__main__":
    main()
