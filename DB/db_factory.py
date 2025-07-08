from config_data.config import Config
from DB.movie_interface import AbstractMovieDB
from DB.movie_sqlite import SQLiteMovieDB
from DB.movie_postgres import PostgresMovieDB


class DBFactory:
    @staticmethod
    def get_db_instance(config: Config) -> AbstractMovieDB:
        if config.db_type == 'sqlite':
            return SQLiteMovieDB()
        elif config.db_type == 'postgres':
            return PostgresMovieDB()
        else:
            raise ValueError(f"Неизвестный тип базы данных: {config.db_type}")
