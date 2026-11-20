from datetime import date, datetime
from typing import Generic, Optional, TypeVar, Union

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt, PositiveInt, model_validator


class ApiModel(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid", allow_inf_nan=False)

    def to_dict(self) -> dict:
        return self.model_dump(mode="json")


class PatchModel(ApiModel):
    @property
    def loaded_fields(self) -> frozenset[str]:
        return frozenset(self.model_fields_set)

    def to_patch(self) -> dict:
        return self.model_dump(mode="json", exclude_unset=True)


class Rating(ApiModel):
    value: Optional[float]
    votes: Optional[NonNegativeInt]
    active: Optional[bool]


class NamedEntity(ApiModel):
    id: PositiveInt
    name: str = Field(min_length=1)


class Money(ApiModel):
    amount: Union[int, float]
    currency_code: Optional[str]
    currency_symbol: Optional[str]


class Image(ApiModel):
    base_url: Optional[str]
    fallback_url: Optional[str]


class Person(ApiModel):
    id: PositiveInt
    name: Optional[str]
    original_name: Optional[str]


class Credits(ApiModel):
    role: str
    people: tuple[Person, ...]
    total: Optional[NonNegativeInt]
    complete: Optional[bool]


class Movie(PatchModel):
    id: PositiveInt
    api_type: str = Field(min_length=1)
    title: str = Field(min_length=1)
    russian_title: Optional[str] = None
    original_title: Optional[str] = None
    content_id: Optional[str] = None
    description: Optional[str] = None
    short_description: Optional[str] = None
    slogan: Optional[str] = None
    release_year: Optional[NonNegativeInt] = None
    end_year: Optional[NonNegativeInt] = None
    duration_minutes: Optional[NonNegativeInt] = None
    episode_duration_minutes: Optional[NonNegativeInt] = None
    rating_kp: Optional[Rating] = None
    rating_imdb: Optional[Rating] = None
    age_rating: Optional[NonNegativeInt] = None
    rating_mpaa: Optional[str] = None
    genres: tuple[NamedEntity, ...] = ()
    countries: tuple[NamedEntity, ...] = ()
    budget: Optional[Money] = None
    fees_world: Optional[Money] = None
    poster: Optional[Image] = None
    credits: tuple[Credits, ...] = ()
    seasons_count: Optional[NonNegativeInt] = None
    episodes_count: Optional[NonNegativeInt] = None


class PartialDate(ApiModel):
    value: Optional[str]
    accuracy: Optional[str]

    @property
    def exact_date(self) -> Optional[date]:
        return date.fromisoformat(self.value) if self.accuracy == "DAY" and self.value else None

    @model_validator(mode="after")
    def validate_exact_date(self):
        if self.accuracy == "DAY" and self.value:
            date.fromisoformat(self.value)
        return self


class Episode(PatchModel):
    id: PositiveInt
    movie_id: PositiveInt
    season_number: NonNegativeInt
    episode_number: PositiveInt
    title: Optional[str] = None
    original_title: Optional[str] = None
    content_id: Optional[str] = None
    description: Optional[str] = None
    release_date: Optional[PartialDate] = None
    availability_date: Optional[datetime] = None
    duration_seconds: Optional[NonNegativeInt] = None


class Season(ApiModel):
    movie_id: PositiveInt
    number: NonNegativeInt
    total: NonNegativeInt
    fetched: NonNegativeInt
    complete: bool


class Relationship(ApiModel):
    movie_id: PositiveInt
    related_movie_id: PositiveInt
    title: Optional[str]
    relationship_type: Optional[str]


T = TypeVar("T")


class Collection(ApiModel, Generic[T]):
    items: tuple[T, ...]
    total: NonNegativeInt
    complete: bool
    scope: str
    limitations: tuple[str, ...]

    @property
    def fetched(self) -> int:
        return len(self.items)


class SeriesEpisodes(ApiModel):
    movie_id: PositiveInt
    seasons: tuple[Season, ...]
    episodes: Collection[Episode]
    online_total: NonNegativeInt


class MovieDetails(ApiModel):
    movie: Movie
    seasons: tuple[Season, ...] = ()
    episodes: Optional[Collection[Episode]] = None
    relationships: Optional[Collection[Relationship]] = None

    @property
    def id(self) -> int:
        return self.movie.id

    @model_validator(mode='after')
    def validate_ownership(self):
        if any(season.movie_id != self.id for season in self.seasons):
            raise ValueError('Season belongs to a different movie')
        numbers = [season.number for season in self.seasons]
        if len(numbers) != len(set(numbers)):
            raise ValueError('Duplicate season number')
        if self.episodes is not None:
            episodes = self.episodes.items
            if any(episode.movie_id != self.id for episode in episodes):
                raise ValueError('Episode belongs to a different movie')
            slots = {(episode.season_number, episode.episode_number) for episode in episodes}
            if len(slots) != len(episodes) or len({episode.id for episode in episodes}) != len(episodes):
                raise ValueError('Duplicate episode identity')
        if self.relationships is not None:
            if any(item.movie_id != self.id or item.related_movie_id == self.id for item in self.relationships.items):
                raise ValueError('Invalid relationship owner or self-reference')
        return self
