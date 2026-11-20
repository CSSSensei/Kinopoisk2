import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import psycopg2
from psycopg2 import sql
from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import SendPhoto
from aiogram.types import Update
from aiogram.utils.formatting import Spoiler, Text
from sqlalchemy.engine import URL

from db.repositories.media import MediaRepository
from db.repositories.telegram import TelegramRepository
from db.connection import create_postgres_engine
from db.ingestion.store import IngestionStore
from parser.graphql.mappers import movie_from_api
from parser.graphql.models import Collection, Fact, MovieDetails
from pydantic import PositiveInt
from telegram_bot.bootstrap import build_dispatcher, run_bot
from telegram_bot.config import BotConfig
from telegram_bot.container import build_container
from telegram_bot.presenters import Section, pages, sections

ROOT = Path(__file__).resolve().parents[1]


class EntryPointTests(unittest.IsolatedAsyncioTestCase):
    def test_direct_script_reaches_config_validation(self):
        result = subprocess.run(
            [sys.executable, "__main__.py"],
            cwd=ROOT / "telegram_bot",
            env={**os.environ, "PYTHONPATH": "", "BOT_TOKEN": ""},
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("ValueError: BOT_TOKEN is required", result.stderr)

    async def test_bootstrap_reaches_polling_without_a_database(self):
        settings = BotConfig("123456:unit-test", "postgresql://localhost:1/catalog")
        with (
            patch.object(BotConfig, "load", return_value=settings),
            patch.object(Dispatcher, "start_polling", new_callable=AsyncMock) as polling,
        ):
            await run_bot()
        polling.assert_awaited_once()


class PaginationTests(unittest.TestCase):
    def test_entity_across_caption_pages(self):
        text = "🎞" * 1200 + "<film>"
        chunks = pages(Text(Spoiler(text)), 1024)
        self.assertEqual("".join(c.text for c in chunks), text)
        for chunk in chunks:
            size = len(chunk.text.encode("utf-16-le")) // 2
            self.assertLessEqual(size, 1024)
            self.assertEqual(chunk.entities[0].length, size)


@unittest.skipUnless(os.getenv("KINOPOISK_TEST_PG_DSN"), "KINOPOISK_TEST_PG_DSN is not set")
class TelegramCatalogTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.admin = psycopg2.connect(os.environ["KINOPOISK_TEST_PG_DSN"])
        cls.admin.autocommit = True
        name = "telegram_catalog_test_" + uuid4().hex
        with cls.admin.cursor() as cur:
            cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))

        def cleanup():
            with cls.admin.cursor() as cur:
                cur.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))
            cls.admin.close()

        cls.addClassCleanup(cleanup)
        params = cls.admin.get_dsn_parameters()
        params["dbname"] = name
        conn = psycopg2.connect(**params)
        cls.addClassCleanup(conn.close)
        cls.settings = BotConfig("123456:unit-test", URL.create(
            "postgresql", username=params["user"], database=name,
            query={"host": params["host"], "port": params["port"]},
        ).render_as_string(hide_password=False), "unit-test-admin-password")
        with conn, conn.cursor() as cur:
            cur.execute((ROOT / "db/sql/create_tables.sql").read_text())
            for version in ("V005__media_ingestion", "V006__media_relations", "V007__telegram_catalog"):
                cur.execute((ROOT / f"db/migrations/{version}.sql").read_text())
            cur.execute("""
                INSERT INTO media(media_id,title,rating,votes,posterurl) VALUES
                    (1,'Present <1>',7,50000,NULL),(2,'Present <2>',6.9,50000,NULL);
                INSERT INTO person(person_id,ru_name) VALUES(111,'Актёр');
                INSERT INTO role(name) VALUES('актеры'),('режиссеры');
                INSERT INTO media_person_role(media_id,person_id,role_id) SELECT 1,111,role_id FROM role;
                INSERT INTO person(person_id, ru_name) VALUES(112,'Другой');
                INSERT INTO media_person_role(media_id,person_id,role_id) SELECT 1,112,role_id FROM role WHERE name='актеры';
                INSERT INTO genre(name) VALUES ('драма'), ('комедия');
                INSERT INTO media_genre SELECT 1,genre_id FROM genre;
                INSERT INTO country(name) VALUES ('США');
                INSERT INTO media_country SELECT 1,country_id FROM country;
                INSERT INTO media_alias VALUES (1,'Alias');
                INSERT INTO media_fact VALUES (1,1,'Секрет сюжета',true);
                INSERT INTO connection_type(name) VALUES ('Продолжение');
                INSERT INTO media_recommendation VALUES (1,2,1),(1,99,2);
                INSERT INTO connected_media SELECT 1,2,connection_type_id FROM connection_type;
                UPDATE media SET age_rating='12+', rating_mpaa='PG-13', top250=4,
                    trailer=to_json('https://example.com/video'::text) WHERE media_id=1;
            """)
            cur.execute((ROOT / "db/migrations/V008__project_namespaces.sql").read_text())

    async def asyncSetUp(self):
        self.container = build_container(self.settings)
        self.addAsyncCleanup(self.container.close)
        self.catalog = await self.container.get(MediaRepository)
        self.users = await self.container.get(TelegramRepository)
        self.dp = build_dispatcher(self.settings, self.catalog, self.users)
        self.bot = Bot(self.settings.token)
        self.addAsyncCleanup(self.bot.session.close)
        self.bot.session.make_request = AsyncMock(return_value=True)
        self.actor = {"id": 1234, "is_bot": False, "first_name": "Имя"}

    async def feed(self, kind, payload):
        update = Update.model_validate({"update_id": 1, kind: payload}, context={"bot": self.bot})
        await self.dp.feed_update(self.bot, update)
        return self.bot.session.make_request.await_args.args[1]

    def message(self, body, user=None):
        return {"message_id": 2, "date": 1000, "from": user or self.actor,
                "chat": {"id": 1234, "type": "private"}, "text": body}

    async def callback(self, data, body="Present (/id_1)", user=None):
        self.bot.session.make_request.reset_mock()
        await self.feed("callback_query", {"id": "cb", "from": user or self.actor, "chat_instance": "1",
                                          "message": self.message(body), "data": data})
        return [call.args[1] for call in self.bot.session.make_request.await_args_list]

    async def test_catalog_card_and_search(self):
        matches = await self.catalog.search("Absent, Alias")
        self.assertEqual([m.media_id for m in matches], [1])
        self.assertEqual(await self.catalog.search(""), [])
        self.assertEqual(await self.catalog.search("%"), [])
        self.assertEqual((await self.catalog.random()).media_id, 1)
        card = await self.catalog.card(1)
        self.assertEqual((card.rating, card.age_rating, card.rating_mpaa, card.top250), (7, "12+", "PG-13", 4))
        self.assertEqual(card.actors, ["Актёр", "Другой"])
        self.assertEqual(card.directors, ["Актёр"])
        self.assertEqual(len(card.genres), 2)
        self.assertEqual(card.countries, ["США"])
        self.assertEqual(len(card.relations), 1)
        self.assertEqual([r["id"] for r in card.similar], [2])
        content = sections(card)
        self.assertIn("Продолжение", content[Section.RELATED].render()[0])
        self.assertIn("/id_2", content[Section.SIMILAR].render()[0])
        self.assertIn("example.com", content[Section.TRAILER].render()[0])
        self.assertIsNone(await self.catalog.card(99))

    async def test_telegram_entry_points(self):
        await self.feed("message", self.message("/start"))
        await self.feed("message", self.message("Найти фильм"))
        answer = await self.feed("message", self.message("Alias"))
        self.assertIn("/id_1", answer.text)
        answer = await self.feed("message", self.message("/id_1"))
        self.assertIn("Present <1>", answer.text)
        self.assertTrue(answer.reply_markup.inline_keyboard)
        random = await self.feed("message", self.message("Рандомный фильм"))
        self.assertIn("/id_1", random.text)
        missing = await self.feed("message", self.message("/id_99"))
        self.assertIn("нет", missing.text)
        for data in ("big_button_4_pressed", "fact:1:0:0"):
            edit, ack = await self.callback(data)
            self.assertEqual(edit.entities[0].type, "spoiler")
            self.assertEqual(ack.__api_method__, "answerCallbackQuery")
        edit, _ = await self.callback("movie:1:2")
        self.assertIn("/id_2", edit.text)
        edit, _ = await self.callback("movie:1:-1")
        self.assertIn("/id_1", edit.text)
        answer = await self.feed("inline_query", {"id": "i", "from": self.actor, "query": "Alias", "offset": ""})
        self.assertEqual(answer.results[0].id, "1")

    async def test_admin(self):
        stranger = {**self.actor, "id": 4567}
        denied, = await self.callback("cut:1:0:1", user=stranger)
        self.assertIn("администратора", denied.text)
        await self.feed("message", self.message(self.settings.admin_password))
        self.assertTrue(await self.users.is_admin(self.actor["id"]))
        await self.feed("message", self.message("запомнить это"))
        await self.feed("message", self.message("/get_users"))
        history = await self.feed("message", self.message("/user_query 1234"))
        self.assertIn("запомнить это", history.text)
        queries = await self.users.queries(0, 100, self.actor["id"])
        self.assertNotIn(self.settings.admin_password, [r["query_text"] for r in queries])

    async def test_graphql_refresh_and_photo_fallback(self):
        engine = create_postgres_engine(self.settings.database_url)
        self.addCleanup(engine.dispose)
        store = IngestionStore(engine)
        store.check_schema(writer=True)
        raw = {"id": 70, "__typename": "Film", "title": {"localized": "Example", "original": "Original"},
               "rating": {"kinopoisk": {"count": 30, "value": 6.0}, "imdb": {"count": 40, "value": 6.5}},
               "ratingLists": {"top250": {"position": 250}}, "mainTrailer": {"id": 11},
               "poster": {"fallbackUrl": "https://example.com/poster.jpg"}}
        def refresh(facts, targets, total):
            token = uuid4()
            movie = MovieDetails(movie=movie_from_api(raw), facts=facts,
                                 similar=Collection[PositiveInt](items=targets, total=total, complete=len(targets)==total,
                                                                 scope="userRecommendations", limitations=()))
            store.enqueue([70], source="test", force=True)
            store.claim(token, 1)
            store.save([movie], token)

        fact = Fact(id=1, text="Fact", is_spoiler=False)
        refresh((fact,), (1, 2), 2)
        refresh((fact,), (1,), 2)
        card = await self.catalog.card(70)
        self.assertEqual((card.votes, card.top250, len(card.facts), len(card.similar)), (30, 250, 1, 2))
        self.assertEqual((await self.catalog.search("Original"))[0].media_id, 70)
        self.bot.session.make_request.side_effect = [
            TelegramBadRequest(method=SendPhoto(chat_id=1, photo="url"), message="failed to get HTTP URL content"), True]
        sent = await self.feed("message", self.message("/id_70"))
        self.assertIn("/id_70", sent.text)
        raw["ratingLists"] = {"top250": None}
        raw["rating"] = {"kinopoisk": {"count": 0}}
        refresh((), (), 0)
        card = await self.catalog.card(70)
        self.assertEqual((card.rating, card.votes, card.top250, card.facts, card.similar), (6.0, 0, None, [], []))
