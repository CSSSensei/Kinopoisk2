import requests
from typing import Dict, List
import random

TOKEN = "28NBDZM-NJ0MHVN-KMPQD9B-RZW80ER"
headers = {"X-API-KEY": TOKEN}


# def get_film(selected):
#     response = requests.get(
#         'https://api.kinopoisk.dev/v1.3/movie',
#         params={
#             'rating.kp' : '1-10',
#             "year": '2010',
#             "sortField" :'rating.kp',
#             "sortType":'-1',
#             "sortField": 'votes.kp',
#             "sortType": '-1',
#             "selectFields": selected,
#             "limit": 100000,
#             "page": 1
#         },
#         headers=headers
#     )
#     movies = response.json()
#     return movies["docs"][:10]
# a = get_film('name rating.kp votes.kp')
#
# for i in a:
#         print(i)

def get_film(n: int) -> List[Dict]:
    if n <= 0:
        print('Неверные входные данные')
        return []
    response = requests.get(
        'https://api.kinopoisk.dev/v1.3/movie',
        params={
            'votes.kp': '15-100000000',
            "sortField": 'votes.kp',
            "sortType": '-1',
            "limit": 250,
            "page": n,
            'selectFields': 'id externalId name alternativeName enName countries poster persons facts videos fees type year rating votes movieLength ratingMpaa ageRating genres budget top10 top250 productionCompanies videos similarMovies sequelsAndPrequels description shortDescription'
        },
        headers=headers
    )
    movies = response.json()
    print(f'{n}. Фильмов найдено: {len(movies["docs"])}')
    return movies["docs"]


def get_id(id: str) -> Dict:
    response = requests.get(
        'https://api.kinopoisk.dev/v1.3/movie/%s' % id,
        headers=headers
    )
    movies = response.json()
    name = movies.get('name')
    print(f'{id}. Фильм найден: {name}')
    return movies

# poster'https://st.kp.yandex.net/images/film_iphone/iphone360_535341.jpg'
