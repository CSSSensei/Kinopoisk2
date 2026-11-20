import unittest
from unittest.mock import Mock, call

from parser.graphql.client import KinopoiskClient
from parser.graphql.errors import EpisodeNotFoundError, KinopoiskAPIError
from parser.graphql.models import Collection, Episode, Movie, Season, SeriesEpisodes
from parser.graphql.operations import Operation


class EpisodeCollectionTests(unittest.TestCase):
    def setUp(self):
        self.client = KinopoiskClient()
        self.client.get_similar = Mock(return_value=None)
        self.client.get_facts = Mock(return_value=None)
        self.client.get_relationships = Mock(return_value=None)
        self.client.get_episode = Mock()
        self.movie = Movie(id=1, title="Series", api_type="TvSeries", content_id="series", seasons_count=1)

    def episode(self, number, **fields):
        return Episode(id=100 + number, movie_id=1, season_number=1, episode_number=number, **fields)

    def collection(self, items, total):
        return Collection[Episode](items=items, total=total, complete=len(items) == total,
                                   scope="test", limitations=("Partial snapshot",) if len(items) < total else ())

    def details(self, metadata, catalog, budget):
        season = Season(movie_id=1, number=1, total=catalog.total, fetched=catalog.fetched, complete=catalog.complete)
        self.client.get_episodes = Mock(return_value=metadata)
        self.client.get_catalog_episodes = Mock(return_value=SeriesEpisodes(
            movie_id=1, seasons=(season,), episodes=catalog, online_total=catalog.fetched,
        ))
        return self.client.get_movie_details(1, movie=self.movie, max_episode_requests=budget)

    def test_merges_loaded_fields_and_fills_gaps_in_order(self):
        metadata = self.collection((self.episode(3, title="Old", description="Synopsis"),), 3)
        catalog = self.collection((self.episode(1), self.episode(3, title="New", description=None)), 3)
        self.client.get_episode.return_value = self.episode(2)
        details = self.details(metadata, catalog, budget=1)
        self.assertTrue(details.episodes.complete)
        self.assertEqual(details.episodes.limitations, ())
        self.assertEqual([e.episode_number for e in details.episodes.items], [1, 2, 3])
        self.assertEqual(details.episodes.items[2].title, "New")
        self.assertEqual(details.episodes.items[2].description, "Synopsis")
        self.assertEqual(details.seasons[0].fetched, 2)
        self.client.get_episode.assert_called_once_with(1, 1, 2)

    def test_conflicting_ids_in_one_position_are_rejected(self):
        metadata = self.collection((self.episode(1),), 1)
        catalog = self.collection((self.episode(1).model_copy(update={"id": 999}),), 1)
        with self.assertRaisesRegex(KinopoiskAPIError, "identity"):
            self.details(metadata, catalog, budget=1)
        self.client.get_episode.assert_not_called()

    def test_exhausted_budget_returns_partial_season(self):
        metadata = self.collection((self.episode(4),), 4)
        self.client.get_episode.side_effect = [EpisodeNotFoundError(), self.episode(2)]
        details = self.details(metadata, self.collection((), 4), budget=2)
        self.assertEqual(self.client.get_episode.call_args_list, [call(1, 1, 1), call(1, 1, 2)])
        self.assertFalse(details.episodes.complete)
        self.assertEqual([e.episode_number for e in details.episodes.items], [2, 4])
        self.assertIn("Stopped at individual episode request budget: 2.", details.episodes.limitations)

    def test_page_budget_is_shared_across_catalog_seasons(self):
        def catalog_response(operation, **variables):
            if operation == Operation.SERIES_BASE_INFO:
                return {"tvSeries": {"id": 1, "contentId": "series", "episodes": {"total": 2},
                                     "seasonsAll": {"total": 2}}}
            if operation == Operation.FILM_PAGE:
                seasons = [{"id": i, "number": i, "contentId": str(i), "episodes": {"total": 1}} for i in (1, 2)]
                return {"movieByContentUuid": {"id": 1, "contentId": "series", "seasons": {"items": seasons}}}
            self.assertEqual(operation, Operation.SEASON_PAGE)
            self.assertEqual((variables["contentId"], variables["offset"]), ("1", 0))
            episode = {"id": 101, "number": 1, "season": {"number": 1, "contentId": "1"}}
            return {"seasonByContentId": {"id": 1, "contentId": "1", "number": 1,
                                          "episodes": {"total": 1, "items": [episode]}}}

        self.client._request = Mock(side_effect=catalog_response)
        catalog = self.client.get_catalog_episodes(1, max_pages=1)
        self.assertEqual(catalog.episodes.fetched, 1)
        self.assertFalse(catalog.episodes.complete)
        self.assertEqual([s.complete for s in catalog.seasons], [True, False])
        self.assertIn("Stopped at the page budget: 1.", catalog.episodes.limitations)
