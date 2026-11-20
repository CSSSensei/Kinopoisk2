from urllib.parse import urlsplit


def web_url(value) -> str | None:
    if isinstance(value, str):
        try:
            url = urlsplit(value)
            if url.scheme in {"http", "https"} and url.hostname:
                return value
        except ValueError:
            pass
    return None


def trailer_links(value):
    if isinstance(value, list):
        for entry in value:
            yield from trailer_links(entry)
    elif isinstance(value, dict):
        yield from trailer_links(value.get("url") or value.get("trailers"))
    elif url := web_url(value):
        yield url
