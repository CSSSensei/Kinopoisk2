from pprint import pprint
from typing import Iterable, Iterator, Optional

from bs4 import BeautifulSoup
from pydantic import PositiveInt

from .episodes import ONLINE_CATALOG_LIMITATION, CatalogSeason, collect_catalog_pages, collect_episodes
from .models import Collection, Episode, Fact, Movie, MovieDetails, Relationship, SeriesEpisodes
from .errors import EpisodeNotFoundError, GraphQLAPIError, KinopoiskAPIError, is_not_found_at
from .mappers import _integer, _object, _text, episode_from_api, movie_from_api
from .operations import BaseInfoRequest, CollectionScope, MovieKind, MovieType, Operation
from .transport import GraphQLTransport


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

    def _request(self, operation: Operation, **variables) -> dict:
        return self.transport.request(operation, **variables)

    def _query(self, operation: Operation, movie_id: int, **variables) -> dict:
        self._positive_integer(movie_id, "movie_id")
        field = "tvSeries" if operation in (Operation.SERIES_EPISODES, Operation.SERIES_BASE_INFO) else "movie"
        root = self._request(operation, **variables).get(field)
        if not isinstance(root, dict) or type(root.get("id")) is not int or root["id"] != movie_id:
            raise KinopoiskAPIError(f"{operation}: missing or mismatched movie ID")
        return root

    def _series_info(self, movie_id: int, episode: tuple[int, int] | None = None) -> dict:
        request = BaseInfoRequest(movie_id)
        return self._query(Operation.SERIES_BASE_INFO, movie_id, **request.series_variables(episode))

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
        if kind not in (None, MovieKind.FILM, MovieKind.SERIES):
            raise ValueError("kind must be film, series or None")
        request = BaseInfoRequest(movie_id, self.actors_limit)
        if kind != MovieKind.SERIES:
            response = self._request(Operation.FILM_BASE_INFO, **request.film_variables())
            raw = response.get("film")
            if isinstance(raw, dict):
                if type(raw.get("id")) is not int or raw["id"] != movie_id or raw.get("__typename") != MovieType.FILM:
                    raise KinopoiskAPIError("FilmBaseInfo: mismatched movie identity")
                return movie_from_api(raw)
            series = response.get("tvSeries")
            if (kind == MovieKind.FILM or not isinstance(series, dict)
                    or type(series.get("id")) is not int or series["id"] != movie_id):
                raise KinopoiskAPIError("FilmBaseInfo: missing or mismatched movie identity")
        raw = self._request(Operation.SERIES_BASE_INFO, **request.series_variables()).get("tvSeries")
        if (not isinstance(raw, dict) or type(raw.get("id")) is not int
                or raw["id"] != movie_id or raw.get("__typename") != MovieType.TV_SERIES):
            raise KinopoiskAPIError("TvSeriesBaseInfo: missing or mismatched movie identity")
        return movie_from_api(raw)

    def iter_movies(self, movie_ids: Iterable[int], *, kind: Optional[str] = None) -> Iterator[Movie]:
        for movie_id in movie_ids:
            yield self.get_movie(movie_id, kind=kind)

    def get_movie_details(self, movie_id: int, *, include_episodes: bool = True, max_episode_pages: int = 1000,
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
        if include_episodes and movie.api_type == MovieType.TV_SERIES:
            metadata = self.get_episodes(movie_id)
            catalog = self.get_catalog_episodes(movie_id, max_pages=max_episode_pages) if movie.content_id else None
            if catalog is not None:
                seasons = catalog.seasons
            episodes = collect_episodes(movie, metadata, catalog.episodes if catalog else None,
                                        max_episode_requests, self.get_episode)
        return MovieDetails(movie=movie, seasons=seasons, episodes=episodes,
                            relationships=self.get_relationships(movie_id, related_count=movie.related_count,
                                                                 sequels_prequels_count=movie.sequels_prequels_count),
                            facts=self.get_facts(movie), similar=self.get_similar(movie))

    def _catalog_section(self, movie, film_operation, series_operation, **variables):
        if movie.api_type == MovieType.TV_SERIES:
            operation, root, key = series_operation, "tvSeries", "tvSeriesId"
        else:
            operation, root, key = film_operation, "film", "filmId"
        result = self._request(operation, **{key: movie.id}, **variables).get(root)
        if not isinstance(result, dict) or type(result.get("id")) is not int or result["id"] != movie.id:
            raise KinopoiskAPIError(f"{operation}: missing or mismatched movie identity")
        return result

    def get_facts(self, movie: Movie) -> tuple[Fact, ...]:
        if movie.facts_count == 0:
            return ()
        facts = {}
        total = None
        while total is None or len(facts) < total:
            offset = len(facts)
            root = self._catalog_section(movie, Operation.FILM_FACTS, Operation.SERIES_FACTS,
                                         triviasType="FACT", triviasLimit=30, triviasOffset=offset)
            count = self._count(root, "trivias")
            if root["trivias"].get("offset") != offset or (total is not None and total != count):
                raise KinopoiskAPIError("Fact pagination changed during collection")
            total = count
            items = self._items(root, "trivias")
            for raw in items:
                fact_id = _integer(raw.get("id"), "trivias.id", 1)
                if fact_id in facts or raw.get("type") != "FACT":
                    raise KinopoiskAPIError("Unexpected or duplicate trivia")
                body = _text(raw.get("text"), "trivias.text")
                if not body:
                    raise KinopoiskAPIError("Missing fact text")
                soup = BeautifulSoup(body, "html.parser")
                for br in soup.find_all("br"):
                    br.replace_with("\n")
                facts[fact_id] = Fact(id=fact_id, text=soup.get_text().strip(), is_spoiler=raw.get("isSpoiler"))
            if len(facts) > total or (not items and offset < total):
                raise KinopoiskAPIError("Incomplete fact pagination")
        return tuple(facts.values())

    def get_similar(self, movie: Movie) -> Collection[PositiveInt]:
        ids = []
        total = 0
        if movie.similar_count != 0:
            root = self._catalog_section(movie, Operation.FILM_SIMILAR, Operation.SERIES_SIMILAR,
                                         similarMoviesLimit=20,
                                         withUserData=False, seasonSubscriptionsSupported=False)
            total = self._count(root, "userRecommendations")
            for raw in self._items(root, "userRecommendations"):
                target = _object(raw.get("movie"), "userRecommendations.movie")
                ids.append(_integer(target.get("id"), "userRecommendations.movie.id", 1))
            if movie.id in ids or len(set(ids)) != len(ids) or len(ids) > total:
                raise KinopoiskAPIError("Invalid or duplicate recommended movie")
        return Collection[PositiveInt](items=tuple(ids), total=total, complete=len(ids) == total,
                                       scope="userRecommendations",
                                       limitations=() if len(ids) == total else ("Result limited by the API.",))

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
            raw = self._series_info(movie_id, (season, episode)).get("episode")
        except GraphQLAPIError as error:
            if error.errors and all(is_not_found_at(item, "tvSeries", "episode") for item in error.errors):
                raise EpisodeNotFoundError(f'Episode not found: {movie_id}/{season}/{episode}') from error
            raise
        if not isinstance(raw, dict):
            raise EpisodeNotFoundError(f'Episode not found: {movie_id}/{season}/{episode}')
        item = episode_from_api(raw, movie_id)
        if item.season_number != season or item.episode_number != episode:
            raise KinopoiskAPIError("Mismatched episode identity")
        return item

    def get_episodes(self, movie_id: int) -> Collection[Episode]:
        root = self._query(Operation.SERIES_EPISODES, movie_id, tvSeriesId=movie_id, episodesLimit=30)
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
            total=total, complete=complete, scope=CollectionScope.METADATA_SNAPSHOT, limitations=limitations,
        )

    def _catalog_seasons(self, page: dict) -> tuple[CatalogSeason, ...]:
        seasons = []
        content_ids, numbers = set(), set()
        for raw in self._items(page, "seasons"):
            season_id = _integer(raw.get("id"), "season.id", 1)
            number = _integer(raw.get("number"), "season.number")
            content_id = raw.get("contentId")
            if not isinstance(content_id, str) or not content_id or content_id in content_ids:
                raise KinopoiskAPIError("Invalid or duplicate season contentId")
            if number in numbers:
                raise KinopoiskAPIError("Duplicate season number")
            content_ids.add(content_id)
            numbers.add(number)
            seasons.append(CatalogSeason(season_id, number, content_id, self._count(raw, "episodes")))
        return tuple(seasons)

    def _season_page(self, movie_id: int, season: CatalogSeason, offset: int) -> tuple[Episode, ...]:
        root = self._request(
            Operation.SEASON_PAGE, contentId=season.content_id,
            limit=20, offset=offset, withPreOrder=False, withUserData=False,
        ).get("seasonByContentId")
        if (not isinstance(root, dict) or type(root.get("id")) is not int
                or type(root.get("number")) is not int or root["id"] != season.id
                or root.get("contentId") != season.content_id
                or root["number"] != season.number):
            raise KinopoiskAPIError("SerialStructureSeason: mismatched season identity")
        if self._count(root, "episodes") != season.episode_count:
            raise KinopoiskAPIError("Episode count changed during pagination")
        items = self._items(root, "episodes")
        if not items or offset + len(items) > season.episode_count:
            raise KinopoiskAPIError("Invalid episode page length")
        episodes = []
        for raw in items:
            episode = episode_from_api(raw, movie_id)
            if raw["season"].get("contentId") != season.content_id or episode.season_number != season.number:
                raise KinopoiskAPIError("Episode belongs to a different season")
            episodes.append(episode)
        return tuple(episodes)

    def get_catalog_episodes(self, movie_id: int, max_pages: int = 20) -> SeriesEpisodes:
        self._positive_integer(max_pages, "max_pages")
        info = self._series_info(movie_id)
        total = self._count(info, "episodes")
        season_count = self._count(info, "seasonsAll")
        content_id = info.get("contentId")
        if content_id is None:
            collection = Collection[Episode](
                items=(), total=total, complete=False,
                scope=CollectionScope.ONLINE_WITH_ANNOUNCEMENTS,
                limitations=(ONLINE_CATALOG_LIMITATION, "The series has no online catalog contentId."),
            )
            return SeriesEpisodes(movie_id=movie_id, seasons=(), episodes=collection, online_total=0)
        if not isinstance(content_id, str) or not content_id:
            raise KinopoiskAPIError("Invalid catalog contentId")
        page = self._request(
            Operation.FILM_PAGE, contentUuid=content_id, isAuthorized=False,
            withPrechosenEpisode=False, episodeNumber=0, seasonNumber=0,
            withUserData=False, socialArgumentLimit=0, includeSocialArgumentTypes=[],
            withExternalViewOptions=False, withPreOrder=False,
        ).get("movieByContentUuid")
        if (not isinstance(page, dict) or type(page.get("id")) is not int
                or page["id"] != movie_id or page.get("contentId") != content_id):
            raise KinopoiskAPIError("FilmPage: mismatched movie identity")
        seasons = self._catalog_seasons(page)
        return collect_catalog_pages(movie_id, seasons, total, season_count, max_pages, self._season_page)

    def get_relationships(self, movie_id: int, *, related_count: Optional[int] = None,
                          sequels_prequels_count: Optional[int] = None) -> Collection[Relationship]:
        self._positive_integer(movie_id, "movie_id")
        variables = {"movieId": movie_id, "relatedMoviesLimit": 20, "withUserData": False}
        operations = []
        no_relationships = related_count == 0 and sequels_prequels_count in (None, 0)
        if not no_relationships:
            if sequels_prequels_count != 0:
                operations.append((Operation.SEQUELS_PREQUELS, "sequelsPrequels"))
            operations.append((Operation.RELATED_MOVIES, "relatedMovies"))
        limitations = ["MovieRelatedMovies does not include relationship types or directions."]
        items = []
        total = 0
        for operation, field in operations:
            root = self._query(operation, movie_id, **variables)
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
                                        scope=CollectionScope.FRONTEND_RELATIONSHIPS, limitations=tuple(limitations))


if __name__ == "__main__":
    client = KinopoiskClient()
    pprint(client.get_movie(687595).__dict__)
