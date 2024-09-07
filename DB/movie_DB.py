import os
import sqlite3
from typing import List, Dict
from random import choice
from config_data.movie_init import Movie

FILMS_DB = f'{os.path.dirname(__file__)}/filmsDB.db'


with sqlite3.connect(FILMS_DB) as connection:
    cur = connection.cursor()
    cur.execute('''
    CREATE TABLE IF NOT EXISTS films_db (
        id INTEGER PRIMARY KEY,
        ru_name TEXT,
        rating_kp REAL,
        votes_kp INTEGER,
        genres TEXT,
        rating_imdb REAL,
        votes_imdb INTEGER,
        imdb TEXT,
        kphd TEXT,
        alternativeName TEXT,
        en_name TEXT,
        type TEXT,
        year INTEGER,
        movieLength INTEGER,
        ratingMpaa TEXT,
        ageRating INTEGER,
        countries TEXT,
        budget_value TEXT,
        fees_world TEXT,
        top10 INTEGER,
        top250 INTEGER,
        productionCompanies TEXT,
        trailer TEXT,
        similarMovies TEXT,
        sequelsAndPrequels TEXT,
        actors TEXT,
        director TEXT,
        description TEXT,
        shortDescription TEXT,
        formula REAL
    )
    ''')

    cur.execute('''
    CREATE TABLE IF NOT EXISTS facts (
        id INTEGER PRIMARY KEY,
        facts TEXT
    )
    ''')

    connection.commit()


def search_name(name: str) -> List[Movie]:
    with sqlite3.connect(FILMS_DB) as conn:
        cursor = conn.cursor()

        # Разделяем введённое имя на слова
        lst = name.replace(',', '').split()

        # Формируем запрос
        query = "SELECT * FROM items WHERE " + " OR ".join(
            ["ru_name LIKE ? OR alternativeName LIKE ? OR en_name LIKE ?"] * len(lst)
        )

        # Подготовка параметров для запроса
        params = [f'%{term}%' for term in lst for _ in range(3)]  # Для каждого термина добавляем 3 параметра "LIKE"

        cursor.execute(query, params)
        results = cursor.fetchall()

        return [Movie(*row) for row in results]


def search_en_name(name: str) -> List[Movie]:
    with sqlite3.connect(FILMS_DB) as conn:
        cursor = conn.cursor()
        parts = name.replace(',', '').split()
        if len(parts) == 0:
            return []
        # Создаем placeholders для поиска с использованием 'AND'
        placeholders = ' OR '.join(['(ru_name LIKE ? OR alternativeName LIKE ? OR en_name LIKE ?)'] * len(parts))
        sql_query = f'SELECT * FROM films_db WHERE {placeholders} ORDER BY formula DESC LIMIT 50'

        # Подготовка параметров для запроса
        params = [f'%{part}%' for part in parts for _ in range(3)]  # Каждое слово трижды для трех колонок
        cursor.execute(sql_query, params)
        results = cursor.fetchall()

    return [Movie(*row) for row in results]


def random_film() -> Movie:
    with sqlite3.connect(FILMS_DB) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM films_db WHERE rating_kp >= 7 AND votes_kp >= 50000')
        rows = cursor.fetchall()
        if rows:
            return Movie(*choice(rows))
        return None


def get_facts(id: int) -> str:
    with sqlite3.connect(FILMS_DB) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT facts FROM facts WHERE id = ?', (id,))
        result = cursor.fetchone()
        return result[0] if result else ''


def search_by_id(id: int) -> Movie:
    with sqlite3.connect(FILMS_DB) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM films_db WHERE id = ?', (id,))
        row = cursor.fetchone()
        return Movie(*row) if row else None


def get_info(movie: Movie) -> List[str]:
    info = []
    info.append(f'<b><a href="https://www.kinopoisk.ru/film/{movie.id}">' + (movie.ru_name if movie.ru_name else movie.alternativeName) + f'</a></b> <i>(/id_{movie.id})</i>\n')
    info.append(f'<b>Рейтинг:</b> {movie.rating_kp}\n' if movie.rating_kp else '')
    info.append(f'<b>{movie.votes_kp} оценок</b>\n' if movie.votes_kp is not None else '')
    info.append(f'<b>Жанры:</b> {movie.genres}\n' if movie.genres else '')
    info.append(f'<b>Тип материала:</b> {movie.type}\n' if movie.type else '')
    info.append(f'<b>{movie.year} год</b>\n' if movie.year != -1 else '')
    info.append(f'<b>Длительность:</b> {movie.movieLength} мин\n' if movie.movieLength != -1 else '')
    info.append(f"<b>Рейтинг MPAA:</b> {movie.ratingMpaa}\n" if movie.ratingMpaa else '')
    info.append(f'<b>Возрастной рейтинг</b> {movie.ageRating}+\n' if movie.ageRating != -1 else '')
    info.append(f'<b>Страна:</b> {movie.countries}\n' if movie.countries else '')
    info.append(f'<b>Бюджет:</b> {movie.budget_value}\n' if movie.budget_value else '')
    info.append(f'<b>Сборы:</b> {movie.fees_world}\n' if movie.fees_world else '')
    info.append(f'<b>Место в топ 10:</b> {movie.top10}\n' if movie.top10 != -1 else '')
    info.append(f'<b>Место в топ 250:</b> {movie.top250}\n' if movie.top250 != -1 else '')
    info.append(f'<b>Продакшн компании:</b> {movie.productionCompanies}\n' if movie.productionCompanies else '')
    info.append(f'<b>Актеры:</b> {movie.actors}\n' if movie.actors else '')
    info.append(f'<b>Режиссер:</b> {movie.director}\n' if movie.director else '')

    description = (f'<code>{movie.description}</code>\n\n' if movie.description else '') + (
        f'<b>Коротко о фильме:</b>\n<code>{movie.shortDescription}</code>\n' if movie.shortDescription else '')

    similar = f'<b>Похожие фильмы:</b>\n{movie.similarMovies.replace("id: ", "/id_")}' if movie.similarMovies else ''
    trailer = movie.trailer if movie.trailer else ''

    short = ''.join(info[0:2]) + info[5] + info[3] + info[9] + info[16]
    sequels = f'<b>Сиквелы и приквелы:</b>\n{movie.sequelsAndPrequels.replace("id: ", "/id_")}\n' if movie.sequelsAndPrequels else ''

    return [short, description, similar, trailer, ''.join(info), sequels, short + '\n' + (movie.shortDescription or movie.description or '\n')]


def filter_database(filters: Dict[str, str | bool]) -> List[Movie]:
    with sqlite3.connect(FILMS_DB) as conn:
        cursor = conn.cursor()
        query = 'SELECT * FROM films_db WHERE 1=1'
        conditions = []
        params = []

        for filter_key, filter_value in filters.items():
            if filter_key == 'top10' and filter_value:
                conditions.append("top10 != -1")
            elif filter_key == 'top250' and filter_value:
                conditions.append("top250 != -1")
            elif filter_key == 'director':
                conditions.append("director LIKE ?")
                params.append(f'%{filter_value.strip()}%')
            elif filter_key == 'actors':
                conditions.append("actors LIKE ?")
                params.append(f'%{filter_value}%')
            elif filter_key == 'name':
                lst = filter_value.replace(',', '').split()
                for name in lst:
                    conditions.append("ru_name LIKE ?")
                    params.append(f'%{name}%')
            elif filter_key == 'year':
                filter_value = filter_value.replace(' ', '')
                if '-' in filter_value:
                    mn, mx = map(int, filter_value.split('-'))
                    conditions.append("year BETWEEN ? AND ?")
                    params.extend([mn, mx])
                else:
                    mn = int(filter_value)
                    conditions.append("year >= ?")
                    params.append(mn)
            elif filter_key == 'genres':
                lst = filter_value.replace(',', '').split()
                for genre in lst:
                    conditions.append("genres LIKE ?")
                    params.append(f'%{genre}%')
            elif filter_key == 'rating_kp':
                filter_value = filter_value.replace(' ', '')
                if '-' in filter_value:
                    mn, mx = map(float, filter_value.split('-'))
                    conditions.append("rating_kp BETWEEN ? AND ?")
                    params.extend([mn, mx])
                else:
                    mn = float(filter_value)
                    conditions.append("rating_kp >= ?")
                    params.append(mn)
            elif filter_key == 'votes_kp':
                filter_value = filter_value.replace(' ', '')
                if '-' in filter_value:
                    mn, mx = map(int, filter_value.split('-'))
                    conditions.append("votes_kp BETWEEN ? AND ?")
                    params.extend([mn, mx])
                else:
                    mn = int(filter_value)
                    conditions.append("votes_kp >= ?")
                    params.append(mn)
            elif filter_key == 'productionCompanies':
                lst = filter_value.replace(',', ' ').strip().split()
                for company in lst:
                    conditions.append("productionCompanies LIKE ?")
                    params.append(f'%{company}%')
            elif filter_key == 'type':
                conditions.append("type LIKE ?")
                params.append(f'%{filter_value}%')
            elif filter_key == 'ratingMpaa':
                conditions.append("ratingMpaa LIKE ?")
                params.append(f'%{filter_value}%')

        if conditions:
            query += ' AND ' + ' AND '.join(conditions)
        cursor.execute(query, params)
        rows = cursor.fetchall()

        return [Movie(*row) for row in rows]



if __name__ == "__main__":


    print(random_film())
    print(search_name('Фильм'))
    print(*[i.__dict__ for i in filter_database({'year': '2019-2020', 'top10': False})], sep='\n')

