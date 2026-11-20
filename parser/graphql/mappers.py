import math
import re
from datetime import datetime

from .models import (
    Credits, Episode, Image, Money, Movie, NamedEntity,
    PartialDate, Person, Rating,
)
from .errors import ResponseValidationError


def _object(value, path):
    if not isinstance(value, dict):
        raise ResponseValidationError(f"{path}: expected an object")
    return value


def _integer(value, path, minimum=0):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ResponseValidationError(f"{path}: expected an integer >= {minimum}")
    return value


def _optional_int(value, path):
    return None if value is None else _integer(value, path)


def _text(value, path):
    if value is not None and not isinstance(value, str):
        raise ResponseValidationError(f"{path}: expected a string or null")
    return value


def _number(value, path):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ResponseValidationError(f"{path}: expected a finite number")
    return value


def _rating(value):
    if value is None:
        return None
    value = _object(value, "rating")
    active = value.get("isActive")
    if active is not None and not isinstance(active, bool):
        raise ResponseValidationError("rating.isActive: expected a boolean")
    fields = {}
    if "value" in value:
        fields["value"] = None if value["value"] is None else _number(value["value"], "rating.value")
    if "count" in value:
        fields["votes"] = _optional_int(value["count"], "rating.count")
    if "isActive" in value:
        fields["active"] = active
    return Rating(**fields)


def _entities(value, path):
    if not isinstance(value, list):
        raise ResponseValidationError(f"{path}: expected a list")
    entities = []
    for item in value:
        item = _object(item, path)
        name = _text(item.get("name"), f"{path}.name")
        if not name:
            raise ResponseValidationError(f"{path}.name: required")
        entities.append(NamedEntity(id=_integer(item.get("id"), f"{path}.id", 1), name=name))
    return tuple(entities)


def _money(value):
    if value is None:
        return None
    value = _object(value, "money")
    currency = _object(value.get("currency") or {}, "money.currency")
    return Money(
        amount=_number(value.get("amount"), "money.amount"),
        currency_code=_text(currency.get("currencyCode"), "money.currencyCode"),
        currency_symbol=_text(currency.get("symbol"), "money.currency.symbol"),
    )


def _url(value):
    value = _text(value, "image URL")
    return "https:" + value if value and value.startswith("//") else value


def _image(value):
    if value is None:
        return None
    value = _object(value, "image")
    return Image(base_url=_url(value.get("avatarsUrl")), fallback_url=_url(value.get("fallbackUrl")))


def _credits(value, role):
    value = _object(value, role)
    if not isinstance(value.get("items"), list):
        raise ResponseValidationError(f"{role}.items: expected a list")
    people = []
    for item in value["items"]:
        person = _object(_object(item, role).get("person"), f"{role}.person")
        original = _text(person.get("originalName"), "person.originalName")
        people.append(Person(
            id=_integer(person.get("id"), "person.id", 1),
            name=_text(person.get("name"), "person.name") or original, original_name=original,
        ))
    total = _optional_int(value.get("total"), f"{role}.total")
    unique = len({person.id for person in people}) == len(people)
    return Credits(role=role, people=tuple(people), total=total,
                      complete=None if total is None else unique and total == len(people))


def movie_from_api(raw):
    raw = _object(raw, "movie")
    movie_id = _integer(raw.get("id"), "movie.id", 1)
    api_type = _text(raw.get("__typename"), "movie.__typename")
    if not api_type:
        raise ResponseValidationError("movie.__typename: required")
    titles = _object(raw.get("title"), "movie.title")
    russian = _text(titles.get("russian"), "title.russian")
    original = _text(titles.get("original"), "title.original")
    title = _text(titles.get("localized"), "title.localized") or russian or original
    if not title:
        raise ResponseValidationError("movie.title: no usable title")
    values = {"id": movie_id, "api_type": api_type, "title": title}
    if "russian" in titles:
        values["russian_title"] = russian
    if "original" in titles:
        values["original_title"] = original
    for target, source in (
        ("content_id", "contentId"), ("description", "synopsis"),
        ("short_description", "shortDescription"), ("slogan", "tagline"),
    ):
        if source in raw:
            values[target] = _text(raw[source], source)
    for target, source in (
        ("release_year", "productionYear"), ("duration_minutes", "duration"),
        ("episode_duration_minutes", "seriesDuration"),
    ):
        if source in raw:
            values[target] = _optional_int(raw[source], source)
    if "releaseYears" in raw:
        years = raw["releaseYears"]
        if not isinstance(years, list):
            raise ResponseValidationError("releaseYears: expected a list")
        starts = [_optional_int(_object(y, "releaseYears").get("start"), "releaseYears.start") for y in years]
        ends = [_optional_int(y.get("end"), "releaseYears.end") for y in years]
        if "productionYear" not in raw:
            values["release_year"] = min((v for v in starts if v is not None), default=None)
        values["end_year"] = max((v for v in ends if v is not None), default=None) if years and all(v is not None for v in ends) else None
    if "rating" in raw:
        ratings = raw["rating"]
        if ratings is None:
            values.update(rating_kp=None, rating_imdb=None, votes_kp=None, votes_imdb=None)
        else:
            ratings = _object(ratings, "rating")
            for target, source in (("rating_kp", "kinopoisk"), ("rating_imdb", "imdb")):
                if source in ratings:
                    entry = ratings[source]
                    rating = _rating(entry)
                    values[target] = rating
                    if entry is None or "count" in entry:
                        values["votes_kp" if source == "kinopoisk" else "votes_imdb"] = rating.votes if rating else None
    if "ratingLists" in raw:
        lists = raw["ratingLists"]
        for name in ("top250", "top10"):
            if lists is None:
                values[name] = None
            elif name in _object(lists, "ratingLists"):
                item = lists[name]
                if item is None:
                    values[name] = None
                elif "position" in _object(item, name):
                    position = item["position"]
                    values[name] = None if position is None else _integer(position, f"{name}.position", 1)
    if "mainTrailer" in raw and raw["mainTrailer"] is None:
        values["trailer_url"] = None
    elif "mainTrailer" in raw:
        trailer = _object(raw["mainTrailer"], "mainTrailer")
        trailer_id = _integer(trailer.get("id"), "mainTrailer.id", 1)
        kind = "series" if api_type == "TvSeries" else "film"
        values["trailer_url"] = f"https://www.kinopoisk.ru/{kind}/{movie_id}/video/{trailer_id}/"
    if "restriction" in raw:
        restriction = raw["restriction"]
        if restriction is None:
            values.update(age_rating=None, rating_mpaa=None)
        else:
            restriction = _object(restriction, "restriction")
            if "age" in restriction:
                age = restriction["age"]
                if age is not None and (not isinstance(age, str) or not re.fullmatch(r"age\d+", age)):
                    raise ResponseValidationError("restriction.age: expected ageN or null")
                values["age_rating"] = int(age[3:]) if age else None
            if "mpaa" in restriction:
                values["rating_mpaa"] = _text(restriction["mpaa"], "restriction.mpaa")
    for key in ("genres", "countries"):
        if key in raw:
            values[key] = _entities(raw[key], key)
    if "boxOffice" in raw:
        box = raw["boxOffice"]
        if box is None:
            values.update(budget=None, fees_world=None)
        else:
            box = _object(box, "boxOffice")
            for target, source in (("budget", "budget"), ("fees_world", "worldBox")):
                if source in box:
                    values[target] = _money(box[source])
    gallery = _object(raw.get("gallery") or {}, "gallery")
    posters = _object(gallery.get("posters") or {}, "gallery.posters")
    if "kpVertical" in posters:
        values["poster"] = _image(posters["kpVertical"])
    elif "poster" in raw:
        values["poster"] = _image(raw["poster"])
    roles = ("actors", "directors", "writers", "producers", "operators", "composers", "designers", "filmEditors")
    credits = tuple(_credits(raw[role], role) for role in roles if role in raw)
    if credits:
        values["credits"] = credits
    for target, source in (("seasons_count", "seasonsAll"), ("episodes_count", "episodes")):
        if source in raw:
            values[target] = _optional_int(_object(raw[source], source).get("total"), source + ".total")
    for target, source in (("facts_count", "factsCount"), ("similar_count", "similarMoviesCount")):
        if source in raw and raw[source] is not None:
            values[target] = _optional_int(_object(raw[source], source).get("total"), source + ".total")
    return Movie(**values)


def episode_from_api(raw, movie_id):
    raw = _object(raw, "episode")
    season = _object(raw.get("season"), "episode.season")
    values = {
        "id": _integer(raw.get("id"), "episode.id", 1),
        "movie_id": _integer(movie_id, "movie_id", 1),
        "season_number": _integer(season.get("number"), "episode.season.number"),
        "episode_number": _integer(raw.get("number"), "episode.number", 1),
    }
    if "title" in raw:
        titles = _object(raw["title"], "episode.title")
        values["title"] = next((_text(titles.get(k), "episode.title." + k) for k in ("localized", "russian", "original") if titles.get(k)), None)
        if "original" in titles:
            values["original_title"] = _text(titles["original"], "episode.title.original")
    for target, source in (("description", "synopsis"), ("content_id", "contentId"), ("content_id", "episodeContentId")):
        if source in raw:
            values[target] = _text(raw[source], source)
    if "releaseDate" in raw:
        release = raw["releaseDate"]
        if release is None:
            values["release_date"] = None
        else:
            release = _object(release, "episode.releaseDate")
            try:
                partial = PartialDate(value=_text(release.get("date"), "releaseDate.date"),
                                         accuracy=_text(release.get("accuracy"), "releaseDate.accuracy"))
            except ValueError as error:
                raise ResponseValidationError("Invalid episode release date") from error
            values["release_date"] = partial
    if "ott" in raw and raw["ott"] is not None:
        ott = _object(raw["ott"], "episode.ott")
        if "duration" in ott:
            values["duration_seconds"] = _optional_int(ott["duration"], "ott.duration")
        if "plannedAvailabilityDate" in ott:
            value = _text(ott["plannedAvailabilityDate"], "ott.plannedAvailabilityDate")
            try:
                values["availability_date"] = datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None
            except ValueError as error:
                raise ResponseValidationError("Invalid availability date") from error
    return Episode(**values)
