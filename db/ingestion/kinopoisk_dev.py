import os
import requests
from dotenv import find_dotenv, load_dotenv
from typing import Dict, List

load_dotenv(find_dotenv())

TOKEN = os.getenv('KINOPOISK_API')
headers = {"X-API-KEY": TOKEN}


def get_film(n: int) -> List[Dict]:
    if n <= 0:
        print('Неверные входные данные')
        return []
    response = requests.get(
        'https://api.kinopoisk.dev/v1.3/movie',
        params={
            'votes.kp': '15000-100000000',
            "sortField": 'votes.kp',
            "sortType": '-1',
            "limit": 250,
            "page": n,
            'selectFields': 'id name slogan logo alternativeName enName countries poster persons facts fees type year rating votes movieLength ratingMpaa ageRating genres budget productionCompanies videos similarMovies sequelsAndPrequels description shortDescription'
        },
        headers=headers
    )
    movies = response.json()
    print(f'{n}. Фильмов найдено: {len(movies["docs"])}')
    return movies["docs"]


def get_film_by_id(id: int) -> Dict:
    response = requests.get(
        'https://api.kinopoisk.dev/v1.3/movie/%s' % str(id),
        headers=headers
    )
    movies = response.json()
    return movies
