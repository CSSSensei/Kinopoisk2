import json
import math
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from threading import Event, Lock
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .errors import GraphQLAPIError, HTTPAPIError, KinopoiskAPIError

ENDPOINT = "https://graphql.kinopoisk.ru/graphql/"


class GraphQLTransport:
    def __init__(self, *, rps=5, timeout=25):
        for name, value in (("rps", rps), ("timeout", timeout)):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be a positive finite number")
        self.timeout = timeout
        self.interval = 1 / rps
        query_dir = Path(__file__).with_name("queries")
        self.queries = {
            path.stem: path.read_text(encoding="utf-8")
            for path in sorted(query_dir.glob("*.graphql"))
        }
        if not self.queries:
            raise FileNotFoundError(f"No GraphQL documents in {query_dir}")
        self._lock = Lock()
        self._last_start = None
        self._blocked_until = 0
        self._cancelled = Event()

    def _wait(self):
        while not self._cancelled.is_set():
            with self._lock:
                now = time.monotonic()
                next_start = self._blocked_until
                if self._last_start is not None:
                    next_start = max(next_start, self._last_start + self.interval)
                delay = next_start - now
                if delay <= 0:
                    self._last_start = now
                    return
            self._cancelled.wait(delay)
        raise KinopoiskAPIError('Transport stopped')

    def defer(self, seconds: float):
        with self._lock:
            self._blocked_until = max(self._blocked_until, time.monotonic() + seconds)

    def cancel_pending(self):
        self._cancelled.set()

    @staticmethod
    def _retry_after(value):
        if not value:
            return None
        try:
            return max(0, int(value))
        except ValueError:
            try:
                deadline = parsedate_to_datetime(value)
                if deadline.tzinfo is None:
                    deadline = deadline.replace(tzinfo=timezone.utc)
                return max(0, (deadline - datetime.now(timezone.utc)).total_seconds())
            except (TypeError, ValueError, OverflowError):
                return None

    def request(self, operation, **variables):
        # Preserve the wire format of the captured frontend documents.
        query = " ".join(line.strip() for line in self.queries[operation].splitlines() if line.strip()) + " "
        request = Request(
            f"{ENDPOINT}?operationName={operation}",
            data=json.dumps({"operationName": operation, "query": query, "variables": variables}).encode("utf-8"),
            headers={
                "Accept": "application/json", "Content-Type": "application/json",
                "Origin": "https://www.kinopoisk.ru", "Referer": "https://www.kinopoisk.ru/",
                "Service-Id": "25", "User-Agent": "Mozilla/5.0",
            },
        )
        self._wait()
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.load(response)
        except HTTPError as error:
            retry_after = self._retry_after(error.headers.get("Retry-After"))
            if retry_after is not None:
                self.defer(retry_after)
            error.close()
            raise HTTPAPIError(operation, error.code, retry_after) from error
        except (URLError, TimeoutError, OSError, ValueError) as error:
            raise KinopoiskAPIError(f"{operation}: {error}") from error
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
            if isinstance(payload, dict) and payload.get("errors"):
                raise GraphQLAPIError(operation, payload["errors"])
            raise KinopoiskAPIError(f"{operation}: expected GraphQL data object")
        data = payload["data"]
        errors = payload.get("errors") or []
        # The site's document probes both types, including film-only SEO for series IDs.
        ignored_paths = []
        if operation == "FilmBaseInfo":
            if isinstance(data.get("film"), dict) and data.get("tvSeries") is None:
                ignored_paths = [["tvSeries"]]
            elif isinstance(data.get("tvSeries"), dict) and data.get("film") is None:
                ignored_paths = [["film"], ["webPage", "kpFilmPage"]]
        if ignored_paths:
            errors = [error for error in errors if not (
                isinstance(error, dict) and error.get("path") in ignored_paths
                and isinstance(error.get("extensions"), dict)
                and error["extensions"].get("code") == "NotFoundError"
            )]
        if errors:
            raise GraphQLAPIError(operation, errors)
        return data
