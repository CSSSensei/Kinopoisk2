import gzip
import io
import re
import time
from typing import Iterator
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from xml.etree import ElementTree


SITEMAP_INDEX = 'https://www.kinopoisk.ru/sitemaps/sitemap.xml'
_NAMESPACE = '{http://www.sitemaps.org/schemas/sitemap/0.9}'
_MOVIE_PATH = re.compile(r'/(?:film|series)/(\d+)/?')
_CATALOG_PATH = re.compile(r'/sitemaps/sitemap_(?:film|series)[\w-]*\.xml(?:\.gz)?')


class SitemapClient:
    def __init__(self, *, timeout: float = 25, max_bytes: int = 64 * 1024 * 1024):
        if timeout <= 0 or max_bytes <= 0:
            raise ValueError('timeout and max_bytes must be positive')
        self.timeout = timeout
        self.max_bytes = max_bytes
        self._last_request = 0.0

    def _read(self, url: str, root_name: str) -> Iterator[dict[str, str]]:
        parsed = urlsplit(url)
        if (parsed.scheme != 'https' or parsed.netloc != 'www.kinopoisk.ru'
                or not parsed.path.startswith('/sitemaps/') or parsed.query or parsed.fragment):
            raise ValueError('Unexpected sitemap URL')
        time.sleep(max(0, self._last_request + 1 - time.monotonic()))
        self._last_request = time.monotonic()
        request = Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Accept-Encoding': 'gzip'})
        with urlopen(request, timeout=self.timeout) as response:
            data = response.read(self.max_bytes + 1)
        if len(data) > self.max_bytes:
            raise ValueError('Sitemap exceeds size limit')
        if data.startswith(b'\x1f\x8b'):
            with gzip.GzipFile(fileobj=io.BytesIO(data)) as archive:
                data = archive.read(self.max_bytes + 1)
            if len(data) > self.max_bytes:
                raise ValueError('Decompressed sitemap exceeds size limit')
        if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
            raise ValueError('Sitemap must not contain XML entities')
        events = ElementTree.iterparse(io.BytesIO(data), events=('start', 'end'))
        _, root = next(events)
        if root.tag != _NAMESPACE + root_name:
            raise ValueError(f'Expected sitemap {root_name}')
        entry_tag = _NAMESPACE + ('sitemap' if root_name == 'sitemapindex' else 'url')
        for event, element in events:
            if event == 'end' and element.tag == entry_tag:
                entry = {child.tag.removeprefix(_NAMESPACE): child.text or '' for child in element}
                if not entry.get('loc'):
                    raise ValueError('Sitemap entry has no location')
                yield entry
                root.clear()

    def catalog_sitemaps(self) -> Iterator[str]:
        seen = set()
        for entry in self._read(SITEMAP_INDEX, 'sitemapindex'):
            url = entry['loc']
            if _CATALOG_PATH.fullmatch(urlsplit(url).path) and url not in seen:
                seen.add(url)
                yield url
        if not seen:
            raise ValueError('No movie or series sitemaps found')

    def movie_ids(self, sitemap_url: str) -> Iterator[int]:
        for entry in self._read(sitemap_url, 'urlset'):
            url = urlsplit(entry['loc'])
            match = _MOVIE_PATH.fullmatch(url.path)
            if url.scheme == 'https' and url.netloc == 'www.kinopoisk.ru' and match:
                movie_id = int(match[1])
                if movie_id > 0:
                    yield movie_id
