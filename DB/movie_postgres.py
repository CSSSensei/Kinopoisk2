from typing import List, Union, Dict
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Text, or_, and_, func
)
from sqlalchemy.orm import sessionmaker, Session, declarative_base

from config_data.models import Movie
from filters.UCommands import cut_string
from config_data.config import load_config
from DB.movie_interface import AbstractMovieDB

config = load_config()
DATABASE_URL = config.database_url

engine = create_engine(DATABASE_URL, echo=False)
Base = declarative_base()
SessionLocal = sessionmaker(bind=engine)


class Film(Base):
    __tablename__ = 'films_db'

    id = Column(Integer, primary_key=True, index=True)
    ru_name = Column(String)
    rating_kp = Column(Float)
    votes_kp = Column(Integer)
    genres = Column(Text)
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
    productionCompanies = Column(Text)
    trailer = Column(String)
    similarMovies = Column(Text)
    sequelsAndPrequels = Column(Text)
    actors = Column(Text)
    director = Column(String)
    description = Column(Text)
    shortDescription = Column(Text)
    formula = Column(Float)
    facts = Column(Text)


class PostgresMovieDB(AbstractMovieDB):
    def __init__(self):
        Base.metadata.create_all(bind=engine)

    def get_session(self) -> Session:
        return SessionLocal()

    def to_model(self, film: Film) -> Movie:
        return Movie(
            film.id, film.ru_name, film.rating_kp, film.votes_kp, film.genres,
            film.rating_imdb, film.votes_imdb, film.imdb, film.kphd,
            film.alternativeName, film.en_name, film.type, film.year,
            film.movieLength, film.ratingMpaa, film.ageRating, film.countries,
            film.budget_value, film.fees_world, film.top10, film.top250,
            film.productionCompanies, film.trailer, film.similarMovies,
            film.sequelsAndPrequels, film.actors, film.director,
            film.description, film.shortDescription, film.formula, film.facts
        )

    def search_by_name(self, name: str) -> List[Movie]:
        session = self.get_session()
        terms = name.replace(',', '').split()
        filters = []
        for term in terms:
            pattern = f"%{term}%"
            filters.append(
                or_(Film.ru_name.ilike(pattern),
                    Film.alternativeName.ilike(pattern),
                    Film.en_name.ilike(pattern))
            )

        query = session.query(Film).filter(or_(*filters))
        results = query.all()
        session.close()
        return [self.to_model(f) for f in results]

    def search_en_name(self, name: str) -> List[Movie]:
        session = self.get_session()
        parts = name.replace(',', '').split()
        if not parts:
            session.close(); return []
        conds = []
        for part in parts:
            p = f"%{part}%"
            conds.append(
                or_(Film.ru_name.ilike(p), Film.alternativeName.ilike(p), Film.en_name.ilike(p))
            )
        query = (
            session.query(Film)
            .filter(or_(*conds))
            .order_by(Film.votes_kp.desc())
            .limit(50)
        )
        results = query.all()
        session.close()
        return [self.to_model(f) for f in results]

    def random_film(self) -> Union[Movie, None]:
        session = self.get_session()
        film = (
            session.query(Film)
            .filter(Film.rating_kp >= 7, Film.votes_kp >= 50000)
            .order_by(func.random())
            .first()
        )
        session.close()
        return self.to_model(film) if film else None

    def get_facts(self, id: int) -> str:
        session = self.get_session()
        film = session.query(Film.facts).filter(Film.id == id).first()
        session.close()
        if not film or not film.facts:
            return ''
        return film.facts.replace('<spoiler>', '<span class="tg-spoiler">').replace('</spoiler>', '</span>')

    def search_by_id(self, id: int) -> Union[Movie, None]:
        session = self.get_session()
        film = session.query(Film).filter(Film.id == id).first()
        session.close()
        return self.to_model(film) if film else None

    def get_info(self, movie: Movie) -> List[str]:
        info = [f'<b><a href="https://www.kinopoisk.ru/film/{movie.id}">' +
                (movie.ru_name or movie.alternativeName) + f'</a></b> <i>(/id_{movie.id})</i>\n',
                f'<b>Рейтинг:</b> {movie.rating_kp}\n' if movie.rating_kp else '',
                f'<b>{movie.year} год</b>\n' if movie.year != -1 else '',
                f'<b>Жанры:</b> {movie.genres}\n' if movie.genres else '',
                f'<b>{movie.votes_kp} оценок</b>\n' if movie.votes_kp is not None else '',
                f'<b>Тип материала:</b> {movie.type}\n' if movie.type else '',
                f'<b>Длительность:</b> {movie.movieLength} мин\n' if movie.movieLength != -1 else '',
                f'<b>Возрастной рейтинг</b> {movie.ageRating}+\n' if movie.ageRating != -1 else '',
                f'<b>Страна:</b> {movie.countries}\n' if movie.countries else '',
                f'<b>Бюджет:</b> {movie.budget_value}\n' if movie.budget_value else '',
                f'<b>Место в топ 250:</b> {movie.top250}\n' if movie.top250 != -1 else '',
                f'<b>Продакшн компании:</b> {cut_string(movie.productionCompanies, 40)}\n' if movie.productionCompanies else '',
                f'<b>Актеры:</b> {cut_string(movie.actors)}\n' if movie.actors else '',
                f'<b>Режиссер:</b> {movie.director}\n' if movie.director else ''
                ]

        description = (f'<blockquote>{movie.description}</blockquote>\n\n' if movie.description else '') + (
            f'<b>Коротко о фильме:</b>\n<i>{movie.shortDescription}</i>\n' if movie.shortDescription else '')

        similar = f'<b>Похожие фильмы:</b>\n{movie.similarMovies.replace("id: ", "/id_")}' if movie.similarMovies else ''
        trailer = movie.trailer or ''
        short = ''.join(info[0:4]) + info[8] + info[13]
        sequels = f'<b>Сиквелы и приквелы:</b>\n{movie.sequelsAndPrequels.replace("id: ", "/id_")}\n' if movie.sequelsAndPrequels else ''

        return [short, description, similar, trailer, ''.join(info), sequels, short + '\n' + (movie.shortDescription or movie.description or '\n')]

    def filter_database(self, filters: Dict[str, Union[str, bool]]) -> List[Movie]:
        session = self.get_session()
        q = session.query(Film)
        for key, value in filters.items():
            if key == 'top10' and value:
                q = q.filter(Film.top10 != -1)
            elif key == 'top250' and value:
                q = q.filter(Film.top250 != -1)
            elif key == 'director':
                q = q.filter(Film.director.ilike(f"%{value.strip()}%"))
            elif key == 'actors':
                q = q.filter(Film.actors.ilike(f"%{value}%"))
            elif key == 'name':
                name_conditions = []
                for name_part in value.replace(',', '').split():
                    name_conditions.append(
                        or_(Film.ru_name.ilike(f"%{name_part}%"),
                            Film.alternativeName.ilike(f"%{name_part}%"),
                            Film.en_name.ilike(f"%{name_part}%"))
                    )
                if name_conditions:
                    q = q.filter(or_(*name_conditions))
            elif key == 'year':
                y = value.replace(' ', '')
                if '-' in y:
                    mn, mx = map(int, y.split('-'))
                    q = q.filter(Film.year.between(mn, mx))
                else:
                    q = q.filter(Film.year >= int(y))
            elif key == 'genres':
                for g in value.replace(',', '').split():
                    q = q.filter(Film.genres.ilike(f"%{g}%"))
            elif key == 'rating_kp':
                r = value.replace(' ', '')
                if '-' in r:
                    mn, mx = map(float, r.split('-'))
                    q = q.filter(Film.rating_kp.between(mn, mx))
                else:
                    q = q.filter(Film.rating_kp >= float(r))
            elif key == 'votes_kp':
                v = value.replace(' ', '')
                if '-' in v:
                    mn, mx = map(int, v.split('-'))
                    q = q.filter(Film.votes_kp.between(mn, mx))
                else:
                    q = q.filter(Film.votes_kp >= int(v))
            elif key == 'productionCompanies':
                for c in value.replace(',', ' ').split():
                    q = q.filter(Film.productionCompanies.ilike(f"%{c}%"))
            elif key == 'type':
                q = q.filter(Film.type.ilike(f"%{value}%"))
            elif key == 'ratingMpaa':
                q = q.filter(Film.ratingMpaa.ilike(f"%{value}%"))
        films = q.all()
        session.close()
        return [self.to_model(f) for f in films]


if __name__ == '__main__':
    db_instance = PostgresMovieDB()
    print(db_instance.random_film().to_dict())