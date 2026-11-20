import logging
from collections.abc import Callable
from dataclasses import dataclass

from .errors import EpisodeNotFoundError, KinopoiskAPIError
from .models import Collection, Episode, Movie, Season, SeriesEpisodes
from .operations import CollectionScope


logger = logging.getLogger(__name__)
ONLINE_CATALOG_LIMITATION = (
    "The catalog selects ONLINE_WITH_ANNOUNCEMENTS and does not include releaseDate. "
    "plannedAvailabilityDate is not an episode premiere date."
)


@dataclass(frozen=True)
class CatalogSeason:
    id: int
    number: int
    content_id: str
    episode_count: int


def merge_episodes(metadata: Collection[Episode], catalog: Collection[Episode] | None) -> dict[tuple[int, int], Episode]:
    records = {(item.season_number, item.episode_number): item for item in metadata.items}
    if len(records) != len(metadata.items):
        raise KinopoiskAPIError('Duplicate episode position in metadata')
    if catalog is None:
        return records
    if catalog.total != metadata.total:
        raise KinopoiskAPIError('Episode count changed between metadata and catalog')
    for item in catalog.items:
        slot = (item.season_number, item.episode_number)
        previous = records.get(slot)
        if previous is None:
            records[slot] = item
            continue
        if previous.id != item.id:
            raise KinopoiskAPIError('Episode identity changed between metadata and catalog')
        values = previous.model_dump(exclude_unset=True)
        for field, value in item.model_dump(exclude_unset=True).items():
            if value is not None or field not in values:
                values[field] = value
        records[slot] = Episode(**values)
    if len(records) > metadata.total:
        raise KinopoiskAPIError('Combined episodes exceed metadata total')
    return records


def collect_episodes(movie: Movie, metadata: Collection[Episode], catalog: Collection[Episode] | None,
                     max_requests: int, fetch_episode: Callable[[int, int, int], Episode]) -> Collection[Episode]:
    records = merge_episodes(metadata, catalog)
    requests = _fill_gaps(movie, records, metadata.total, max_requests, fetch_episode)
    complete = len(records) == metadata.total
    limitations = ()
    if not complete:
        catalog_limits = catalog.limitations if catalog is not None else ('No online catalog contentId.',)
        limitations = tuple(dict.fromkeys(metadata.limitations + catalog_limits))
        if requests >= max_requests:
            limitations += (f'Stopped at individual episode request budget: {max_requests}.',)
    return Collection[Episode](items=tuple(records[slot] for slot in sorted(records)),
                               total=metadata.total, complete=complete, scope=CollectionScope.SERIES_EPISODES,
                               limitations=limitations)


def _fill_gaps(movie: Movie, records: dict[tuple[int, int], Episode], total: int,
               max_requests: int, fetch_episode: Callable[[int, int, int], Episode]) -> int:
    if len(records) == total or max_requests == 0:
        return 0
    known_max: dict[int, int] = {}
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
                item = fetch_episode(movie.id, season, number)
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


def collect_catalog_pages(movie_id: int, seasons: tuple[CatalogSeason, ...], total: int, season_count: int,
                          max_pages: int, fetch_page: Callable[[int, CatalogSeason, int], tuple[Episode, ...]]) -> SeriesEpisodes:
    limitations = [ONLINE_CATALOG_LIMITATION]
    online_total = sum(season.episode_count for season in seasons)
    records, summaries, seen = [], [], set()
    pages = 0
    for season in seasons:
        expected = season.episode_count
        offset = 0
        while offset < expected and pages < max_pages:
            items = fetch_page(movie_id, season, offset)
            pages += 1
            for item in items:
                if item.id in seen:
                    raise KinopoiskAPIError("Duplicate episode: pagination did not advance")
                seen.add(item.id)
                records.append(item)
            offset += len(items)
        summaries.append(Season(movie_id=movie_id, number=season.number,
                                total=expected, fetched=offset, complete=offset == expected))
    pages_complete = all(season.complete for season in summaries)
    complete = pages_complete and len(seasons) == season_count and len(records) == online_total == total
    if not pages_complete:
        limitations.append(f"Stopped at the page budget: {max_pages}.")
    if online_total != total or len(seasons) != season_count:
        limitations.append("The online catalog does not cover all metadata seasons or episodes.")
    collection = Collection[Episode](
        items=tuple(records), total=total, complete=complete,
        scope=CollectionScope.ONLINE_WITH_ANNOUNCEMENTS, limitations=tuple(limitations),
    )
    return SeriesEpisodes(movie_id=movie_id, seasons=tuple(summaries),
                         episodes=collection, online_total=online_total)
