import os
import unittest
from unittest.mock import Mock
from uuid import uuid4

from tests.catalog_database import catalog_database
from db.connection import create_postgres_engine
from db.ingestion.pipeline import MovieWorker, WorkerOptions
from db.ingestion.store import IngestionStore
from parser.graphql.models import Collection, Movie, MovieDetails, Relationship


@unittest.skipUnless(os.getenv("KINOPOISK_TEST_PG_DSN"), "KINOPOISK_TEST_PG_DSN is not set")
class IngestionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        engine = create_postgres_engine(cls.enterClassContext(catalog_database()))
        cls.addClassCleanup(engine.dispose)
        cls.store = IngestionStore(engine)

    def setUp(self):
        with self.store.transaction() as cursor:
            cursor.execute("TRUNCATE media_ingestion_job, media CASCADE")

    def movie(self, movie_id, **fields):
        return Movie(id=movie_id, api_type="Film", title=str(movie_id), **fields)

    def run_related(self, max_movies=None):
        link = Relationship(movie_id=1, related_movie_id=2, relationship_type="AFTER", title="2")
        root = MovieDetails(movie=self.movie(1), relationships=Collection[Relationship](
            items=(link,), total=1, complete=True, scope="test", limitations=(),
        ))
        client = Mock()
        client.get_movie_details.side_effect = [root, MovieDetails(movie=self.movie(2))]
        self.store.enqueue([1], source="test")
        options = WorkerOptions(workers=1, batch_size=10, max_movies=max_movies)
        return MovieWorker(self.store, client, options).run()

    def test_final_batch_discovers_and_resolves_related_movie(self):
        self.assertEqual(self.run_related(), 2)
        with self.store.transaction() as cursor:
            cursor.execute("SELECT media_id, parent_id FROM connected_media")
            self.assertEqual(cursor.fetchall(), [(1, 2)])

    def test_final_batch_respects_claim_limit(self):
        self.assertEqual(self.run_related(max_movies=1), 1)
        with self.store.transaction() as cursor:
            cursor.execute("SELECT state, attempts FROM media_ingestion_job WHERE media_id=2")
            self.assertEqual(cursor.fetchone(), ("pending", 0))

    def test_expired_lease_cannot_write_or_finish_job(self):
        old, new = uuid4(), uuid4()
        self.store.enqueue([1], source="test")
        self.store.claim(old, 1, lease_seconds=0)
        self.assertEqual(self.store.save([self.movie(1)], old), 0)
        self.assertEqual(self.store.claim(new, 1), [(1, 2)])
        self.assertEqual(self.store.save([self.movie(1)], old), 0)
        with self.store.transaction() as cursor:
            cursor.execute("SELECT count(*) FROM media")
            self.assertEqual(cursor.fetchone(), (0,))
        self.assertEqual(self.store.save([self.movie(1)], new), 1)

    def test_low_vote_cards_are_deferred_without_updating_last_success(self):
        self.store.enqueue([1, 2], source="test")
        token = uuid4()
        self.store.claim(token, 2)
        self.assertEqual(self.store.save([self.movie(1, votes_kp=2), self.movie(2, votes_kp=1)],
                                         token, min_votes=1), 1)
        with self.store.transaction() as cursor:
            cursor.execute("""SELECT media_id, state, last_success_at IS NOT NULL, next_attempt_at > now()
                              FROM media_ingestion_job ORDER BY media_id""")
            self.assertEqual(cursor.fetchall(), [(1, "pending", True, True), (2, "pending", False, True)])
            cursor.execute("SELECT media_id FROM media")
            self.assertEqual(cursor.fetchall(), [(1,)])

    def test_invalid_rating_fails_only_its_own_job(self):
        self.store.enqueue([1, 2], source="test")
        client = Mock()
        client.get_movie_details.side_effect = lambda movie_id, **kwargs: MovieDetails(
            movie=self.movie(movie_id, age_rating=1 if movie_id == 1 else 12))
        worker = MovieWorker(self.store, client, WorkerOptions(workers=1, batch_size=2))
        self.assertEqual(worker.run(), 1)
        with self.store.transaction() as cursor:
            cursor.execute("SELECT state, last_error FROM media_ingestion_job WHERE media_id=1")
            self.assertEqual(cursor.fetchone(), ("failed", "Unsupported age rating: 1"))
            cursor.execute("SELECT media_id FROM media")
            self.assertEqual(cursor.fetchall(), [(2,)])
