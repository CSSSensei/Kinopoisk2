import logging
from typing import Iterable, Iterator, Optional

from .models import Collection, Episode, Movie, MovieDetails, Relationship, Season, SeriesEpisodes
from .errors import EpisodeNotFoundError, GraphQLAPIError, KinopoiskAPIError
from .mappers import _integer, _object, _text, episode_from_api, movie_from_api
from .transport import GraphQLTransport

from pprint import pprint


logger = logging.getLogger(__name__)


class KinopoiskClient:
    def __init__(self, *, rps: float = 5, timeout: float = 25, actors_limit: int = 20):
        if isinstance(actors_limit, bool) or not isinstance(actors_limit, int) or not 0 <= actors_limit <= 30:
            raise ValueError("actors_limit must be between 0 and 30")
        self.transport = GraphQLTransport(rps=rps, timeout=timeout)
        self.actors_limit = actors_limit

    @staticmethod
    def _positive_integer(value: int, name: str) -> None:
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"{name} must be a positive integer")

    def _request(self, operation: str, **variables) -> dict:
        return self.transport.request(operation, **variables)

    def _query(self, operation: str, movie_id: int, **variables) -> dict:
        self._positive_integer(movie_id, "movie_id")
        field = "tvSeries" if operation in ("TvSeriesEpisodes", "TvSeriesBaseInfo") else "movie"
        root = self._request(operation, **variables).get(field)
        if not isinstance(root, dict) or type(root.get("id")) is not int or root["id"] != movie_id:
            raise KinopoiskAPIError(f"{operation}: missing or mismatched movie ID")
        return root

    @staticmethod
    def _base_variables(actors_limit: int) -> dict:
        return {
            "isAuthorized": False, "actorsLimit": actors_limit,
            "voiceOverActorsLimit": 0, "relatedMoviesLimit": 0,
            "catchupsLimit": 0, "includeSocialArgumentTypes": [], "socialArgumentLimit": 0,
        }

    def _series_info(self, movie_id: int, season: Optional[int] = None,
                     episode: Optional[int] = None) -> dict:
        return self._query(
            "TvSeriesBaseInfo", movie_id, **self._base_variables(0),
            tvSeriesId=movie_id, withExternalViewOptions=False,
            withPrechosenEpisode=season is not None and episode is not None,
            seasonNumber=season if season is not None else 0,
            episodeNumber=episode if episode is not None else 0,
        )

    @staticmethod
    def _count(root: dict, field: str) -> int:
        collection = root.get(field)
        total = collection.get("total") if isinstance(collection, dict) else None
        if isinstance(total, bool) or not isinstance(total, int) or total < 0:
            raise KinopoiskAPIError(f"Invalid count: {field}")
        return total

    @staticmethod
    def _items(root: dict, field: str) -> list[dict]:
        collection = root.get(field)
        if not isinstance(collection, dict) or not isinstance(collection.get("items"), list):
            raise KinopoiskAPIError(f"Missing collection: {field}")
        items = collection["items"]
        if any(not isinstance(item, dict) for item in items):
            raise KinopoiskAPIError(f"Invalid records: {field}")
        return items

    def get_movie(self, movie_id: int, *, kind: Optional[str] = None) -> Movie:
        self._positive_integer(movie_id, "movie_id")
        if kind not in (None, "film", "series"):
            raise ValueError("kind must be film, series or None")
        variables = self._base_variables(self.actors_limit)
        if kind != "series":
            response = self._request("FilmBaseInfo", filmId=movie_id, **variables)
            raw = response.get("film")
            if isinstance(raw, dict):
                if type(raw.get("id")) is not int or raw["id"] != movie_id or raw.get("__typename") != "Film":
                    raise KinopoiskAPIError("FilmBaseInfo: mismatched movie identity")
                return movie_from_api(raw)
            series = response.get("tvSeries")
            if (kind == "film" or not isinstance(series, dict)
                    or type(series.get("id")) is not int or series["id"] != movie_id):
                raise KinopoiskAPIError("FilmBaseInfo: missing or mismatched movie identity")
        variables.update(tvSeriesId=movie_id, withExternalViewOptions=False,
                         withPrechosenEpisode=False, seasonNumber=0, episodeNumber=0)
        raw = self._request("TvSeriesBaseInfo", **variables).get("tvSeries")
        if (not isinstance(raw, dict) or type(raw.get("id")) is not int
                or raw["id"] != movie_id or raw.get("__typename") != "TvSeries"):
            raise KinopoiskAPIError("TvSeriesBaseInfo: missing or mismatched movie identity")
        return movie_from_api(raw)

    def iter_movies(self, movie_ids: Iterable[int], *, kind: Optional[str] = None) -> Iterator[Movie]:
        for movie_id in movie_ids:
            yield self.get_movie(movie_id, kind=kind)

    def get_movie_details(self, movie_id: int, *, max_episode_pages: int = 1000,
                          max_episode_requests: int = 20000, movie: Optional[Movie] = None) -> MovieDetails:
        self._positive_integer(movie_id, 'movie_id')
        self._positive_integer(max_episode_pages, 'max_episode_pages')
        if type(max_episode_requests) is not int or max_episode_requests < 0:
            raise ValueError('max_episode_requests must be a nonnegative integer')
        if movie is None:
            movie = self.get_movie(movie_id)
        elif movie.id != movie_id:
            raise ValueError('movie does not match movie_id')
        seasons = ()
        episodes = None
        if movie.api_type == 'TvSeries':
            metadata = self.get_episodes(movie_id)
            catalog = self.get_catalog_episodes(movie_id, max_pages=max_episode_pages) if movie.content_id else None
            merged = {(item.season_number, item.episode_number): item for item in metadata.items}
            if catalog is not None:
                seasons = catalog.seasons
                for item in catalog.episodes.items:
                    slot = (item.season_number, item.episode_number)
                    old = merged.get(slot)
                    if old is not None and old.id != item.id:
                        raise KinopoiskAPIError('Episode identity changed between metadata and catalog')
                    values = old.model_dump(exclude_unset=True) if old else {}
                    for field, value in item.model_dump(exclude_unset=True).items():
                        if value is not None or field not in values:
                            values[field] = value
                    merged[slot] = Episode(**values)
            total = metadata.total
            if catalog is not None and catalog.episodes.total != total:
                raise KinopoiskAPIError('Episode count changed between metadata and catalog')
            if len(merged) > total:
                raise KinopoiskAPIError('Combined episodes exceed metadata total')
            requests = self._complete_episodes(movie, merged, total, max_episode_requests)
            complete = len(merged) == total
            limitations = () if complete else tuple(dict.fromkeys(
                metadata.limitations + (catalog.episodes.limitations if catalog else ('No online catalog contentId.',))
            ))
            if not complete and requests >= max_episode_requests:
                limitations += (f'Stopped at individual episode request budget: {max_episode_requests}.',)
            episodes = Collection[Episode](items=tuple(merged[slot] for slot in sorted(merged)),
                                           total=total, complete=complete, scope='series_episodes',
                                           limitations=limitations)
        return MovieDetails(movie=movie, seasons=seasons, episodes=episodes,
                            relationships=self.get_relationships(movie_id))

    def _complete_episodes(self, movie: Movie, records: dict, total: int, max_requests: int) -> int:
        if len(records) == total or max_requests == 0:
            return 0
        known_max = {}
        for season, number in records:
            known_max[season] = max(known_max.get(season, 0), number)
        last_season = max(movie.seasons_count or 0, max(known_max, default=1))
        first_season = 0 if 0 in known_max else 1
        seen = {item.id for item in records.values()}
        requests = 0
        logger.info('[EPISODE FETCH] media_id=%s fetched=%s total=%s filling missing episodes', movie.id, len(records), total)
        for season in range(first_season, last_season + 1):
            number = 1
            while len(records) < total and requests < max_requests:
                slot = (season, number)
                if slot in records:
                    number += 1
                    continue
                requests += 1
                try:
                    item = self.get_episode(movie.id, season, number)
                except EpisodeNotFoundError:
                    # A gap before a known episode does not mark the end of a season.
                    if number >= known_max.get(season, 0):
                        break
                else:
                    if item.id in seen:
                        raise KinopoiskAPIError('Episode ID repeated across season positions')
                    seen.add(item.id)
                    records[slot] = item
                    if requests % 50 == 0 or len(records) == total:
                        logger.info('[EPISODE FETCH] media_id=%s fetched=%s total=%s requests=%s',
                                    movie.id, len(records), total, requests)
                number += 1
            if len(records) == total or requests >= max_requests:
                break
        return requests

    def iter_movie_batches(self, movie_ids: Iterable[int], *, batch_size: int = 100,
                          kind: Optional[str] = None) -> Iterator[tuple[Movie, ...]]:
        self._positive_integer(batch_size, "batch_size")
        batch = []
        for movie in self.iter_movies(movie_ids, kind=kind):
            batch.append(movie)
            if len(batch) == batch_size:
                yield tuple(batch)
                batch.clear()
        if batch:
            yield tuple(batch)

    def get_episode(self, movie_id: int, season: int, episode: int) -> Episode:
        if isinstance(season, bool) or not isinstance(season, int) or season < 0:
            raise ValueError("season must be a nonnegative integer")
        self._positive_integer(episode, "episode")
        try:
            raw = self._series_info(movie_id, season, episode).get("episode")
        except GraphQLAPIError as error:
            if error.errors and all(isinstance(item, dict) and item.get('path') == ['tvSeries', 'episode']
                                    and isinstance(item.get('extensions'), dict)
                                    and item['extensions'].get('code') == 'NotFoundError' for item in error.errors):
                raise EpisodeNotFoundError(f'Episode not found: {movie_id}/{season}/{episode}') from error
            raise
        if not isinstance(raw, dict):
            raise EpisodeNotFoundError(f'Episode not found: {movie_id}/{season}/{episode}')
        item = episode_from_api(raw, movie_id)
        if item.season_number != season or item.episode_number != episode:
            raise KinopoiskAPIError("Mismatched episode identity")
        return item

    def get_episodes(self, movie_id: int) -> Collection[Episode]:
        root = self._query("TvSeriesEpisodes", movie_id, tvSeriesId=movie_id, episodesLimit=30)
        total = root.get("episodesCount")
        if isinstance(total, bool) or not isinstance(total, int) or total < 0:
            raise KinopoiskAPIError("Invalid episode count")
        items = tuple(episode_from_api(raw, movie_id) for field in ("releasedEpisodes", "futureEpisodes")
                      for raw in self._items(root, field))
        if len({item.id for item in items}) != len(items) or len(items) > total:
            raise KinopoiskAPIError("Invalid or duplicate episode list")
        complete = len(items) == total
        limitations = () if complete else (
            "The query returns at most 30 released and 30 future episodes without an offset parameter.",
        )
        return Collection[Episode](
            items=tuple(sorted(items, key=lambda item: (item.season_number, item.episode_number))),
            total=total, complete=complete, scope="metadata_snapshot", limitations=limitations,
        )

    def _season_page(self, season: dict, offset: int) -> dict:
        root = self._request(
            "SerialStructureSeason", contentId=season["contentId"],
            limit=20, offset=offset, withPreOrder=False, withUserData=False,
        ).get("seasonByContentId")
        if (not isinstance(root, dict) or type(root.get("id")) is not int
                or type(root.get("number")) is not int or root["id"] != season["id"]
                or root.get("contentId") != season["contentId"]
                or root.get("number") != season["number"]):
            raise KinopoiskAPIError("SerialStructureSeason: mismatched season identity")
        return root

    def get_catalog_episodes(self, movie_id: int, max_pages: int = 20) -> SeriesEpisodes:
        self._positive_integer(max_pages, "max_pages")
        info = self._series_info(movie_id)
        total = self._count(info, "episodes")
        season_count = self._count(info, "seasonsAll")
        limitations = [
            "The catalog selects ONLINE_WITH_ANNOUNCEMENTS and does not include releaseDate. "
            "plannedAvailabilityDate is not an episode premiere date."
        ]
        content_id = info.get("contentId")
        if content_id is None:
            limitations.append("The series has no online catalog contentId.")
            collection = Collection[Episode](
                items=(), total=total, complete=False,
                scope="ONLINE_WITH_ANNOUNCEMENTS", limitations=tuple(limitations),
            )
            return SeriesEpisodes(movie_id=movie_id, seasons=(), episodes=collection, online_total=0)
        if not isinstance(content_id, str) or not content_id:
            raise KinopoiskAPIError("Invalid catalog contentId")
        page = self._request(
            "FilmPage", contentUuid=content_id, isAuthorized=False,
            withPrechosenEpisode=False, episodeNumber=0, seasonNumber=0,
            withUserData=False, socialArgumentLimit=0, includeSocialArgumentTypes=[],
            withExternalViewOptions=False, withPreOrder=False,
        ).get("movieByContentUuid")
        if (not isinstance(page, dict) or type(page.get("id")) is not int
                or page["id"] != movie_id or page.get("contentId") != content_id):
            raise KinopoiskAPIError("FilmPage: mismatched movie identity")
        seasons = self._items(page, "seasons")
        season_ids, season_numbers = set(), set()
        for season in seasons:
            _integer(season.get("id"), "season.id", 1)
            number = _integer(season.get("number"), "season.number")
            value = season.get("contentId")
            if not isinstance(value, str) or not value or value in season_ids:
                raise KinopoiskAPIError("Invalid or duplicate season contentId")
            season_ids.add(value)
            if number in season_numbers:
                raise KinopoiskAPIError("Duplicate season number")
            season_numbers.add(number)
        online_total = sum(self._count(season, "episodes") for season in seasons)
        records, summaries, seen = [], [], set()
        pages = 0
        for season in seasons:
            expected = self._count(season, "episodes")
            offset = 0
            while offset < expected and pages < max_pages:
                root = self._season_page(season, offset)
                pages += 1
                if self._count(root, "episodes") != expected:
                    raise KinopoiskAPIError("Episode count changed during pagination")
                items = self._items(root, "episodes")
                if not items or offset + len(items) > expected:
                    raise KinopoiskAPIError("Invalid episode page length")
                for raw in items:
                    item = episode_from_api(raw, movie_id)
                    if (raw["season"].get("contentId") != season["contentId"]
                            or item.season_number != season["number"]):
                        raise KinopoiskAPIError("Episode belongs to a different season")
                    if item.id in seen:
                        raise KinopoiskAPIError("Duplicate episode: pagination did not advance")
                    seen.add(item.id)
                    records.append(item)
                offset += len(items)
            summaries.append(Season(movie_id=movie_id, number=season["number"],
                                       total=expected, fetched=offset, complete=offset == expected))
        pages_complete = all(season.complete for season in summaries)
        complete = pages_complete and len(seasons) == season_count and len(records) == online_total == total
        if not pages_complete:
            limitations.append(f"Stopped at the page budget: {max_pages}.")
        if online_total != total or len(seasons) != season_count:
            limitations.append("The online catalog does not cover all metadata seasons or episodes.")
        collection = Collection[Episode](
            items=tuple(records), total=total, complete=complete,
            scope="ONLINE_WITH_ANNOUNCEMENTS", limitations=tuple(limitations),
        )
        return SeriesEpisodes(movie_id=movie_id, seasons=tuple(summaries),
                                 episodes=collection, online_total=online_total)

    def get_relationships(self, movie_id: int) -> Collection[Relationship]:
        variables = {"movieId": movie_id, "relatedMoviesLimit": 20, "withUserData": False}
        sequels = self._query("TouchMovieSequelsPrequels", movie_id, **variables)
        others = self._query("MovieRelatedMovies", movie_id, **variables)
        limitations = ["MovieRelatedMovies does not include relationship types or directions."]
        items = []
        total = 0
        for root, field in ((sequels, "sequelsPrequels"), (others, "relatedMovies")):
            records = self._items(root, field)
            count = self._count(root, field)
            if len(records) > count:
                raise KinopoiskAPIError("Invalid relationship count")
            total += count
            if len(records) < count:
                limitations.append(f"{field} is limited to 20 records without an offset parameter.")
            for raw in records:
                related = _object(raw.get("movie"), "relationship.movie")
                title = _object(related.get("title"), "relationship.movie.title")
                items.append(Relationship(
                    movie_id=movie_id, related_movie_id=_integer(related.get("id"), "relationship.movie.id", 1),
                    title=_text(title.get("russian"), "title.russian") or _text(title.get("original"), "title.original"),
                    relationship_type=_text(raw.get("relationType"), "relationType"),
                ))
        return Collection[Relationship](items=tuple(items), total=total, complete=False,
                                               scope="frontend_relationships", limitations=tuple(limitations))


if __name__ == "__main__":
    client = KinopoiskClient()
    pprint(client.get_movie(687595).__dict__)
