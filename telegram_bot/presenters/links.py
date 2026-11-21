from urllib.parse import urlsplit

from db.repositories.media import MediaSummary


def web_url(value) -> str | None:
    if isinstance(value, str):
        try:
            url = urlsplit(value)
            if url.scheme in {"http", "https"} and url.hostname:
                return value
        except ValueError:
            pass
    return None


def poster_url(movie: MediaSummary, *, preview: bool = False) -> str:
    if preview:
        return (web_url(movie.posterurlpreview) or web_url(movie.posterurl)
                or f"https://st.kp.yandex.net/images/film_iphone/iphone360_{movie.media_id}.jpg")
    return (web_url(movie.posterurl) or web_url(movie.posterurlpreview)
            or f"https://st.kp.yandex.net/images/film_big/{movie.media_id}.jpg")


def trailer_links(value):
    if isinstance(value, list):
        for entry in value:
            yield from trailer_links(entry)
    elif isinstance(value, dict):
        yield from trailer_links(value.get("url") or value.get("trailers"))
    elif url := web_url(value):
        yield url
