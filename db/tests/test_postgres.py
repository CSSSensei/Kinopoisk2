import importlib
import os
import tempfile
import types
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import fasteners
import pgserver
from sqlalchemy import delete, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from config_data.models import Query, User
from db.connection import close_database, create_postgres_engine, get_engine, initialize_database
from db.models import Base, Film, QueryRecord, UserRecord
from db.repositories.movies import MovieRepository
from db.repositories.users import UserRepository


class PostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix="kinopoisk-postgres-", dir="/private/tmp")
        root = Path(cls.directory.name)
        pgserver.PostgresServer.runtime_path = root / "runtime"
        pgserver.PostgresServer.lock_path = root / "runtime.lock"
        pgserver.PostgresServer._lock = fasteners.InterProcessLock(root / "runtime.lock")
        cls.server = pgserver.get_server(root / "data", cleanup_mode="delete")
        cls.engine = create_postgres_engine(cls.server.get_uri())
        cls.sessions = sessionmaker(bind=cls.engine, expire_on_commit=False)
        Base.metadata.create_all(cls.engine)

    @classmethod
    def tearDownClass(cls):
        close_database()
        cls.engine.dispose()
        cls.server.cleanup()
        cls.directory.cleanup()

    def setUp(self):
        with self.engine.begin() as connection:
            for table in (QueryRecord.__table__, UserRecord.__table__, Film.__table__):
                connection.execute(delete(table))
        self.users = UserRepository(self.sessions)
        self.movies = MovieRepository(self.sessions)

    def add_user(self, user_id=9000000001, **kwargs):
        return self.users.add_user(User(user_id=user_id, **kwargs))

    def test_big_telegram_ids_and_timezone(self):
        user = self.add_user(username="first")
        self.assertEqual(self.users.get_user(user.user_id).username, "first")
        self.assertEqual(user.registration_date.utcoffset(), timedelta(hours=3))

    def test_registration_upsert_preserves_admin_and_registration_date(self):
        original = self.add_user(username="before", is_admin=True)
        updated = self.add_user(username="after", is_admin=False)
        self.assertEqual(updated.username, "after")
        self.assertTrue(updated.is_admin)
        self.assertEqual(updated.registration_date, original.registration_date)

    def test_concurrent_registration_is_atomic(self):
        self.add_user(is_admin=True)
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda number: self.add_user(username=f"name-{number}"), range(8)))
        self.assertEqual(len(list(self.users.get_all_users())), 1)
        self.assertTrue(self.users.get_user(9000000001).is_admin)

    def test_admin_changes_and_unknown_users(self):
        self.add_user()
        self.assertTrue(self.users.set_admin(9000000001))
        self.assertEqual([user.user_id for user in self.users.get_admins()], [9000000001])
        self.assertTrue(self.users.set_admin(9000000001, False))
        self.assertFalse(self.users.set_admin(42))
        self.assertIsNone(self.users.get_user(42))
        self.assertIsNone(self.users.update_user(User(user_id=42)))

    def test_update_user(self):
        original = self.add_user(username="before")
        updated = self.users.update_user(User(user_id=original.user_id, username="after", is_admin=True))
        self.assertEqual(updated.username, "after")
        self.assertTrue(updated.is_admin)
        self.assertEqual(updated.registration_date, original.registration_date)

    def test_query_returning_order_limits_and_related_user(self):
        user = self.add_user(username="query-user")
        first = self.users.add_query(Query(user_id=user.user_id, query_text="O'Reilly"))
        second = self.users.add_query(Query(user_id=user.user_id, query_text="second"))
        self.assertEqual(self.users.get_query(first.query_id).query_text, "O'Reilly")
        self.assertEqual(self.users.get_query(first.query_id).user.username, "query-user")
        self.assertEqual(self.users.get_last_queries(1)[0].query_id, second.query_id)
        self.assertEqual(list(self.users.get_all_queries(0)), [])
        self.assertEqual(list(self.users.get_user_queries(user.user_id, 0)), [])
        with self.assertRaises(ValueError):
            self.users.get_last_queries(-1)

    def test_nested_reads_do_not_invalidate_user_iteration(self):
        for user_id in (1, 2, 3):
            self.add_user(user_id)
            self.users.add_query(Query(user_id=user_id, query_text=str(user_id)))
        results = [(user.user_id, len(list(self.users.get_user_queries(user.user_id)))) for user in self.users.get_all_users()]
        self.assertEqual(sorted(results), [(1, 1), (2, 1), (3, 1)])

    def test_delete_user_cascades_queries(self):
        user = self.add_user()
        query = self.users.add_query(Query(user_id=user.user_id, query_text="test"))
        self.assertTrue(self.users.delete_user(user.user_id))
        self.assertIsNone(self.users.get_query(query.query_id))
        self.assertFalse(self.users.delete_user(user.user_id))

    def test_delete_queries(self):
        user = self.add_user()
        first = self.users.add_query(Query(user_id=user.user_id, query_text="first"))
        self.users.add_query(Query(user_id=user.user_id, query_text="second"))
        self.assertTrue(self.users.delete_query(first.query_id))
        self.assertFalse(self.users.delete_query(first.query_id))
        self.assertEqual(self.users.delete_user_queries(user.user_id), 1)
        self.assertIsNotNone(self.users.get_user(user.user_id))

    def test_constraint_failure_does_not_poison_the_pool(self):
        with self.assertRaises(IntegrityError):
            self.users.add_query(Query(user_id=42, query_text="unknown user"))
        self.assertEqual(self.add_user().user_id, 9000000001)
        self.assertEqual(self.engine.pool.checkedout(), 0)

    def add_films(self):
        with self.sessions.begin() as session:
            session.add_all([
                Film(id=795847, ru_name="Кухня в Париже", en_name="Kitchen in Paris", year=2014,
                     rating_kp=7.1, votes_kp=100000, genres="комедия", facts="<spoiler>fact</spoiler>",
                     movieLength=106, ageRating=18, top10=-1, top250=-1),
                Film(id=2, ru_name="Other", rating_kp=5, votes_kp=100, year=2020),
            ])

    def test_movie_search_filters_and_rendering(self):
        self.add_films()
        self.assertEqual(self.movies.search_en_name("PARIS")[0].id, 795847)
        self.assertEqual(self.movies.search_by_name("Кухня")[0].id, 795847)
        self.assertEqual([movie.id for movie in self.movies.filter_database({"year": "2010-2015"})], [795847])
        self.assertEqual(self.movies.random_film().id, 795847)
        self.assertIsNone(self.movies.search_by_id(42))
        self.assertEqual(self.movies.get_facts(795847), '<span class="tg-spoiler">fact</span>')
        self.assertIn("Кухня в Париже", self.movies.get_info(self.movies.search_by_id(795847))[0])
        self.assertEqual(self.engine.pool.checkedout(), 0)

    def test_movie_session_closes_on_invalid_filter(self):
        with self.assertRaises(ValueError):
            self.movies.filter_database({"year": "invalid"})
        self.assertEqual(self.engine.pool.checkedout(), 0)

    def test_shared_runtime_initialization_and_legacy_loaders(self):
        close_database()
        with patch.dict(os.environ, {"DATABASE_URL": self.server.get_uri()}):
            initialize_database()
            self.assertIs(get_engine(), get_engine())
            self.assertIs(MovieRepository().session_factory, UserRepository().session_factory)
            self.assertTrue({"films_db", "telegram_users", "telegram_queries"}.issubset(inspect(get_engine()).get_table_names()))
            for module_name in ("db.ingestion.fill_movies", "db.ingestion.fill_connections"):
                manager = importlib.import_module(module_name).DatabaseManager()
                with manager.get_connection().cursor() as cursor:
                    cursor.execute("SELECT 1")
                    self.assertEqual(cursor.fetchone(), (1,))
                manager.close_connection()
            self.assertEqual(get_engine().pool.checkedout(), 0)
        close_database()

    def test_handler_imports_use_postgres_without_connecting(self):
        from config_data import config as settings

        lexicon = types.ModuleType("lexicon.lexicon")
        lexicon.LEXICON_RU = {"_password": "test-only"}
        environment = {"DATABASE_URL": self.server.get_uri(), "BOT_TOKEN": "123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi"}
        close_database()
        with patch.dict(os.environ, environment), patch.dict("sys.modules", {"lexicon.lexicon": lexicon}):
            with patch.object(settings, "config", settings.load_config()):
                for name in ("handlers.commands", "handlers.inline_handler", "handlers.user_handlers", "handlers.callbacks", "handlers.admin_handlers", "main"):
                    importlib.import_module(name)
            self.assertEqual(get_engine().pool.checkedout(), 0)
        close_database()


class PostgresConfigTests(unittest.TestCase):
    def test_non_postgres_urls_are_rejected(self):
        for value in (None, "", "mysql://user:password@localhost/db"):
            with self.subTest(url=value), self.assertRaises(ValueError):
                create_postgres_engine(value)

    def test_postgres_urls_use_one_sync_driver(self):
        for value in ("postgres://test@localhost/test", "postgresql://test@localhost/test", "postgresql+asyncpg://test@localhost/test"):
            engine = create_postgres_engine(value)
            self.assertEqual(engine.url.drivername, "postgresql+psycopg2")
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
