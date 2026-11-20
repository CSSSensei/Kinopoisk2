import logging
import math
import random
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
from uuid import uuid4

from psycopg2 import DataError, IntegrityError
from pydantic import ValidationError

from db.ingestion.ratings import UnsupportedRating
from db.ingestion.store import IngestionStore, votes_above
from parser.graphql.client import KinopoiskClient
from parser.graphql.errors import HTTPAPIError, ResponseValidationError
from parser.graphql.models import MovieDetails


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WorkerOptions:
    workers: int = 4
    batch_size: int = 500
    flush_seconds: float = 30
    refresh_days: float = 14
    max_attempts: int = 8
    max_movies: int | None = None
    episode_pages: int = 1000
    episode_requests: int = 20000
    min_votes: int | None = None

    def __post_init__(self):
        for name in ('workers', 'batch_size', 'max_attempts', 'episode_pages'):
            if type(getattr(self, name)) is not int or getattr(self, name) <= 0:
                raise ValueError(f'{name} must be a positive integer')
        for name in ('flush_seconds', 'refresh_days'):
            value = getattr(self, name)
            if isinstance(value, bool) or not math.isfinite(value) or value <= 0:
                raise ValueError(f'{name} must be positive and finite')
        if self.max_movies is not None and (type(self.max_movies) is not int or self.max_movies <= 0):
            raise ValueError('max_movies must be a positive integer')
        if type(self.episode_requests) is not int or self.episode_requests < 0:
            raise ValueError('episode_requests must be a nonnegative integer')
        if self.min_votes is not None and (type(self.min_votes) is not int or self.min_votes < 0):
            raise ValueError('min_votes must be a nonnegative integer')


class MovieWorker:
    def __init__(self, store: IngestionStore, client: KinopoiskClient,
                 options: WorkerOptions = WorkerOptions()):
        self.store = store
        self.client = client
        self.options = options

    def _fetch(self, movie_id: int, *, existing: bool = False) -> MovieDetails:
        movie = None
        if self.options.min_votes is not None and not existing:
            movie = self.client.get_movie(movie_id)
            if movie.id != movie_id:
                raise ValueError('API returned a different movie ID')
            if not votes_above(movie, self.options.min_votes):
                return MovieDetails(movie=movie)
        arguments = {'movie': movie} if movie is not None else {}
        details = self.client.get_movie_details(movie_id, max_episode_pages=self.options.episode_pages,
                                                max_episode_requests=self.options.episode_requests, **arguments)
        if details.id != movie_id:
            raise ValueError('API returned a different movie ID')
        return details

    def _failure(self, token, movie_id, attempt, error):
        permanent = isinstance(error, (ResponseValidationError, ValidationError, ValueError))
        if isinstance(error, HTTPAPIError):
            permanent = 400 <= error.status_code < 500 and error.status_code not in (408, 429)
        delay = min(3600, 30 * 2 ** min(attempt - 1, 7)) * random.uniform(1, 1.2)
        if isinstance(error, HTTPAPIError) and error.retry_after is not None:
            delay = max(delay, error.retry_after)
        transport = getattr(self.client, 'transport', None)
        if isinstance(error, HTTPAPIError) and error.status_code == 429 and transport is not None:
            transport.defer(delay)
        terminal = permanent or attempt >= self.options.max_attempts
        self.store.fail(token, movie_id, error=str(error), delay=delay, terminal=terminal)
        logger.warning('movie=%s attempt=%s state=%s error=%s', movie_id, attempt,
                       'failed' if terminal else 'retry', type(error).__name__)
        if isinstance(error, HTTPAPIError) and error.status_code in (401, 403):
            raise RuntimeError(f'API access rejected with HTTP {error.status_code}; ingestion stopped') from error

    def _save(self, movies, token):
        try:
            return self.store.save(movies, token, refresh_days=self.options.refresh_days,
                                   min_votes=self.options.min_votes)
        except (DataError, IntegrityError, UnsupportedRating) as error:
            if len(movies) > 1:
                middle = len(movies) // 2
                return self._save(movies[:middle], token) + self._save(movies[middle:], token)
            reason = str(error) if isinstance(error, UnsupportedRating) else f'{type(error).__name__}: SQLSTATE {error.pgcode}'
            self.store.fail(token, movies[0].id, error=reason, delay=0, terminal=True)
            logger.error('movie=%s rejected: %s', movies[0].id, reason)
            return 0

    def run(self) -> int:
        self.store.check_schema(writer=True)
        with self.store.worker_lock():
            return self._run()

    def _run(self) -> int:
        token = uuid4()
        options = self.options
        pending = {}
        buffer = []
        claimed = saved = 0
        buffer_started = None
        heartbeat_at = time.monotonic()
        executor = ThreadPoolExecutor(max_workers=options.workers, thread_name_prefix='kinopoisk')
        try:
            while True:
                now = time.monotonic()
                if now - heartbeat_at >= 30:
                    self.store.renew(token)
                    heartbeat_at = now
                if buffer and (len(buffer) >= options.batch_size or now - buffer_started >= options.flush_seconds):
                    saved += self._save(buffer, token)
                    logger.info('Saved batch=%s total=%s', len(buffer), saved)
                    buffer.clear()
                    buffer_started = None
                capacity = min(options.workers - len(pending), options.batch_size - len(buffer) - len(pending))
                if options.max_movies is not None:
                    capacity = min(capacity, options.max_movies - claimed)
                jobs = self.store.claim(token, capacity) if capacity > 0 else []
                existing = (self.store.existing_media_ids([movie_id for movie_id, _ in jobs])
                            if jobs and options.min_votes is not None else set())
                for movie_id, attempt in jobs:
                    claimed += 1
                    if attempt > options.max_attempts:
                        self.store.fail(token, movie_id, error='Lease expired after maximum attempts', delay=0, terminal=True)
                        continue
                    pending[executor.submit(self._fetch, movie_id, existing=movie_id in existing)] = (movie_id, attempt)
                if not pending:
                    if buffer:
                        saved += self._save(buffer, token)
                        buffer.clear()
                        buffer_started = None
                        continue
                    if jobs:
                        continue
                    break
                done, _ = wait(pending, timeout=1, return_when=FIRST_COMPLETED)
                for future in done:
                    movie_id, attempt = pending.pop(future)
                    try:
                        movie = future.result()
                    except Exception as error:
                        self._failure(token, movie_id, attempt, error)
                    else:
                        if not buffer:
                            buffer_started = time.monotonic()
                        buffer.append(movie)
            logger.info('Finished: claimed=%s saved=%s', claimed, saved)
            return saved
        finally:
            try:
                transport = getattr(self.client, 'transport', None)
                if pending and transport is not None:
                    transport.cancel_pending()
                executor.shutdown(wait=True, cancel_futures=True)
            finally:
                self.store.release(token)
