# import sqlite3
from typing import List, Set, Any, Dict
import pandas as pd
from pandas import DataFrame

from sqlalchemy import create_engine, Column, Integer, String, Float, ColumnElement

from sqlalchemy.orm import sessionmaker, declarative_base

from get_row import get_row
from черновик import get_film

engine = create_engine('mysql+pymysql://root:root@localhost:3306/new_schema')
Session = sessionmaker(bind=engine)
session = Session()
Base = declarative_base()


class Facts(Base):
    __tablename__ = 'facts'
    id = Column(Integer, primary_key=True)
    facts = Column(String)


class Film(Base):
    __tablename__ = 'films_db'
    id = Column(Integer, primary_key=True)
    ru_name = Column(String)
    rating_kp = Column(Float)
    votes_kp = Column(Integer)
    genres = Column(String)
    rating_imdb = Column(Float)
    votes_imdb = Column(Integer)
    imdb = Column(String)
    kphd = Column(String)
    alternativeName = Column(String)
    en_name = Column(String)
    type = Column(String)
    year = Column(Integer)
    movieLength = Column(Integer)
    ratingMpaa = Column(String)
    ageRating = Column(Integer)
    countries = Column(String)
    budget_value = Column(String)
    fees_world = Column(String)
    top10 = Column(Integer)
    top250 = Column(Integer)
    productionCompanies = Column(String)
    trailer = Column(String)
    similarMovies = Column(String)
    sequelsAndPrequels = Column(String)
    actors = Column(String)
    director = Column(String)
    description = Column(String)
    shortDescription = Column(String)
    formula = Column(Float)


def add_film_to_db(dataframe: DataFrame) -> None:
    dataframe.to_sql('films_db', engine, if_exists='append', index=False)


def add_facts(dataframe: DataFrame) -> None:
    dataframe.to_sql('facts', engine, if_exists='append', index=False)


def add_films_workbench(start: int = 1, finish: int = 201) -> None:
    results = session.query(Film.id).all()
    id_set: Set[int] = set([int(row[0]) for row in results])
    films_data, facts_data = [], []
    for x in range(start, finish):
        items: List = get_film(x)
        cnt = 0
        item: Dict
        for item in items:
            if int(item['id']) in id_set:
                print("Фильм уже существует в базе данных.")
                continue
            id_set.add(int(item['id']))
            cnt += 1
            row: Dict[str, Any] = get_row(item)
            ft = {
                'id': row['id'],
                'facts': row['facts']
            }
            del row['facts']
            films_data.append(row)
            facts_data.append(ft)
        print(f'Фильмов добавлено: {cnt}')
    add_film_to_db(pd.DataFrame(films_data))
    add_facts(pd.DataFrame(facts_data))
    print('Файлы сохранены')


add_films_workbench(650, 710)


def add_sqlite(data: Dict, cnt: int) -> None: #sqlite3
    conn = sqlite3.connect('db.db')
    cursor = conn.cursor()
    # Перед добавлением новой строки, проверяем, что в колонке 'id' нет такого значения
    id_to_insert = data['id']
    cursor.execute("SELECT id FROM my_table1 WHERE id = ?", (id_to_insert,))
    row = cursor.fetchone()

    if row is None:
        # Если строка с заданным id не найдена, добавляем новую строку в базу данных
        cursor.execute(
            "INSERT INTO my_table1 (ru_name, rating_kp, votes_kp, genres, rating_imdb, votes_imdb, id, imdb, kphd, alternativeName, en_name, type, year, movieLength, ratingMpaa, ageRating, countries, budget_value, fees_world, top10, top250, facts, productionCompanies, trailer, similarMovies, sequelsAndPrequels, actors, director, description, shortDescription, formula) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (tuple(data.values())))
        conn.commit()
        print(f'Фильм №{cnt} добавлен')
    else:
        print("Строка с таким id уже существует")

    # Закрываем курсор и соединение с базой данных
    cursor.close()
    conn.close()


def extend_db(start: int = 1, finish: int = 201) -> None: #sqlite3
    for x in range(start, finish):
        items: list = get_film(x)
        item: dict
        cnt = 0
        for item in items:
            cnt += 1
            row = get_row(item)
            add_sqlite(row, cnt)
        print(f'Фильмов добавлено: {cnt}')

# extend_db(533, 550)
