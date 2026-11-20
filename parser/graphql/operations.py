from dataclasses import dataclass
from enum import StrEnum


class Operation(StrEnum):
    FILM_BASE_INFO = "FilmBaseInfo"
    SERIES_BASE_INFO = "TvSeriesBaseInfo"
    SERIES_EPISODES = "TvSeriesEpisodes"
    FILM_PAGE = "FilmPage"
    SEASON_PAGE = "SerialStructureSeason"
    SEQUELS_PREQUELS = "TouchMovieSequelsPrequels"
    RELATED_MOVIES = "MovieRelatedMovies"
    FILM_FACTS = "FilmTrivias"
    SERIES_FACTS = "TvSeriesTrivias"
    FILM_SIMILAR = "FilmSimilarMovies"
    SERIES_SIMILAR = "TvSeriesSimilarMovies"


class MovieKind(StrEnum):
    FILM = "film"
    SERIES = "series"


class MovieType(StrEnum):
    FILM = "Film"
    TV_SERIES = "TvSeries"


class CollectionScope(StrEnum):
    SERIES_EPISODES = "series_episodes"
    METADATA_SNAPSHOT = "metadata_snapshot"
    ONLINE_WITH_ANNOUNCEMENTS = "ONLINE_WITH_ANNOUNCEMENTS"
    FRONTEND_RELATIONSHIPS = "frontend_relationships"


@dataclass(frozen=True)
class BaseInfoRequest:
    movie_id: int
    actors_limit: int = 0

    def _common_variables(self) -> dict:
        return {
            "isAuthorized": False,
            "actorsLimit": self.actors_limit,
            "voiceOverActorsLimit": 0,
            "relatedMoviesLimit": 0,
            "catchupsLimit": 0,
            "includeSocialArgumentTypes": [],
            "socialArgumentLimit": 0,
        }

    def film_variables(self) -> dict:
        return {"filmId": self.movie_id, **self._common_variables()}

    def series_variables(self, episode: tuple[int, int] | None = None) -> dict:
        season_number, episode_number = episode if episode is not None else (0, 0)
        return {
            **self._common_variables(),
            "tvSeriesId": self.movie_id,
            "withExternalViewOptions": False,
            "withPrechosenEpisode": episode is not None,
            "seasonNumber": season_number,
            "episodeNumber": episode_number,
        }
