import unittest
from unittest.mock import Mock

from parser.graphql.client import KinopoiskClient
from parser.graphql.errors import KinopoiskAPIError
from parser.graphql.mappers import movie_from_api
from parser.graphql.operations import Operation


class GraphQLCatalogTests(unittest.TestCase):
    def movie(self, **fields):
        return movie_from_api({"id": 435, "__typename": "Film", "title": {"localized": "Example"}, **fields})

    def test_rank_and_vote_patch(self):
        movie = self.movie(ratingLists={"top10": None, "top250": {"position": 3}},
                           rating={"kinopoisk": {"count": 0}, "imdb": {"value": 8.6, "count": 42}},
                           mainTrailer={"id": 13494})
        self.assertEqual(movie.top250, 3)
        self.assertEqual(movie.votes_kp, 0)
        self.assertEqual(movie.votes_imdb, 42)
        self.assertIn("top10", movie.to_patch())
        self.assertNotIn("top10", self.movie().to_patch())
        self.assertNotIn("value", movie.rating_kp.model_fields_set)
        self.assertTrue(movie.trailer_url.endswith("/435/video/13494/"))
        self.assertNotIn("trailer_url", self.movie().to_patch())
        self.assertIsNone(self.movie(mainTrailer=None).to_patch()["trailer_url"])

    def test_facts_follow_server_offset_and_keep_spoilers(self):
        def page(offset, text):
            return {"film": {"id": 435, "trivias": {"total": 2, "offset": offset, "items": [
                {"id": offset + 7, "type": "FACT", "text": text, "isSpoiler": bool(offset)}]}}}
        client = KinopoiskClient()
        client._request = Mock(side_effect=[page(0, 'A <a href="/x/">B</a>'), page(1, "C &amp; D")])
        facts = client.get_facts(self.movie())
        self.assertEqual([(f.text, f.is_spoiler) for f in facts], [("A B", False), ("C & D", True)])
        client._request.assert_called_with(Operation.FILM_FACTS, filmId=435, triviasType="FACT",
                                           triviasLimit=30, triviasOffset=1)

    def test_truncated_recommendations_and_broken_fact_page(self):
        client = KinopoiskClient()
        client._request = Mock(return_value={"tvSeries": {"id": 1, "userRecommendations": {
            "total": 3, "items": [{"movie": {"id": 2}}]}}})
        series = movie_from_api({"id": 1, "__typename": "TvSeries", "title": {"original": "Series"}})
        result = client.get_similar(series)
        self.assertFalse(result.complete)
        self.assertEqual(result.items, (2,))
        client._request.assert_called_once_with(Operation.SERIES_SIMILAR, tvSeriesId=1, similarMoviesLimit=20,
                                                withUserData=False, seasonSubscriptionsSupported=False)
        client._request = Mock(return_value={"film": {"id": 435, "trivias": {"offset": 0, "total": 2, "items": []}}})
        with self.assertRaises(KinopoiskAPIError):
            client.get_facts(self.movie())
