AGE_RATINGS = {str(age): f"{age}+" for age in (0, 6, 12, 16, 18)}
MPAA_RATINGS = {
    "G": "G",
    "PG": "PG",
    "PG13": "PG-13",
    "PG-13": "PG-13",
    "R": "R",
    "NC17": "NC-17",
    "NC-17": "NC-17",
}


def normalize_age_rating(value):
    if value is None:
        return None
    try:
        return AGE_RATINGS[str(value).removesuffix("+")]
    except KeyError:
        raise ValueError(f"Unsupported age rating: {value!r}") from None


def normalize_mpaa_rating(value):
    if value is None:
        return None
    try:
        return MPAA_RATINGS[str(value).upper()]
    except KeyError:
        raise ValueError(f"Unsupported MPAA rating: {value!r}") from None
