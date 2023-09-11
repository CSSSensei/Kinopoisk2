import requests
import random
TOKEN = "28NBDZM-NJ0MHVN-KMPQD9B-RZW80ER"
headers = {"X-API-KEY": TOKEN}

def get_random_movie(genres, year_range):
    response = requests.get(
        'https://api.kinopoisk.dev/v1.3/movie',
        params={
            "genre.name": genres,
            "limit": 1,
            "page": 1,
            "year": year_range
        },
        headers=headers
    )
    movies = response.json()
    total_pages = movies["total"] // movies["limit"] + (1 if movies["total"] % movies["limit"] > 0 else 0)

    random_page = random.randint(1, total_pages)

    response = requests.get(
        'https://api.kinopoisk.dev/v1.3/movie',
        params={
            "genre.name": genres,
            "limit": 1,
            "page": random_page,
            "year": year_range
        },
        headers=headers
    )
    movies = response.json()
    return movies["docs"][0]
print(get_random_movie([],'2020'))
# year_range = "2023"
# year_range = "2020-2023"
#
# genres = ["боевик", "драма"]
# или чтобы исключить жанр
# genres = ["!боевик"]
# genres = []
# movie = get_random_movie(genres, year_range)
# print(movie)