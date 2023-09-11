from typing import Any, Dict, List

#
# row = db.loc[db['ru_name'] == 'Газовый свет'].squeeze()  # Получаем строку по условию
# clean_row = row.apply(lambda x: str(x).strip())  # Применяем метод strip() к каждому элементу строки
#
# print(clean_row)
#
#
# row_index = db.loc[db['ru_name'] == 'Газовый свет'].index[0]  # Получаем индекс строки по условию
# rating_kp_value = db.at[row_index, 'rating_kp']  # Получаем значение ячейки rating_kp по индексу строки
# print(rating_kp_value)

# best = db[(db['rating_kp']>7) & (db['year']>2010)&(db['rating_imdb']>7) ] ###  сортировка по значению столбцов, по возрастанию и вывод определнных столбцов
# sorted_df = best.sort_values(by='rating_kp',ascending=False)
# print(sorted_df[['ru_name','rating_kp','rating_imdb','year','countries']])


# db.rename(columns={'rating':'rating_imdb'},inplace=True) ###переименовать столбец
# db.to_csv(r'C:\Users\tomin\Downloads\films2.csv', index=False)


# best = db[db['rating_kp']>db['rating_kp'].max()-1].sort_values(by='rating_kp',ascending=False)  # вывесть лучшие 5 фильмов
# selected_rows = best[:5]
# selected_rows_dict = selected_rows.to_dict(orient='records')
# name, rat, y, des =[],[],[],[]
# for i in selected_rows_dict:
#     name.append(i['ru_name'])
#     rat.append(i['rating_kp'])
#     y.append(i['year'])
#     des.append(i['description'])
# msn = max([len(c) for c in name])+1
# msr = max([len(str(c)) for c in rat])+1
# msy = max([len(str(c)) for c in y])+1
# msd = max([len(c) for c in des])+1
# for i in range(5):
#     print(name[i].ljust(msn),end=' ')
#     print(str(rat[i]).ljust(msr),end=' ')
#     print(str(y[i]).ljust(msy), end=' ')
#     print(des[i].ljust(msd), end=' ')
#     print()


from sqlalchemy import create_engine, Column, Integer, String, Float, or_
from sqlalchemy.orm import sessionmaker, declarative_base, Query
from sqlalchemy.sql import func
from random import choice

Base = declarative_base()

# Создание соединения с базой данных
engine = create_engine('mysql+pymysql://root:root@localhost:3306/new_schema')
Session = sessionmaker(bind=engine)
session = Session()


class Database(Base):
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

class Facts(Base):
    __tablename__ = 'facts'
    id = Column(Integer, primary_key=True)
    facts = Column(String)
# Запрос к базе данных
# results = session.query(Database).filter(Database.genres.like('%триллер%')).order_by(Database.rating_kp.desc()).limit(100).all()
#
# # Вывод результатов
# for row in results:
#     name = row.ru_name if row.ru_name is not None else row.alternativeName
#     l = len(row.ru_name) if row.ru_name is not None else len(row.alternativeName)
#     print(f'{name + " " * (25 - l)}|| {row.director} | {row.genres}, {row.rating_kp}, {row.year}')


def search_name(database: session, name: str) -> List[Database]:
    query: Query[Database] = database.query(Database)
    lst = name.replace(',', '').split()
    for i in lst:
        query = query.filter(Database.ru_name.like(f'%{i}%'))
    query = query.order_by(Database.formula.desc())

    results: List[Database] = query.limit(20).all()
    return results


def search_en_name(database: session, name: str) -> List[Database]:
    query: Query[Database] = database.query(Database)
    lst = name.replace(',', '').split()
    for i in lst:
        query = query.filter(or_(Database.ru_name.like(f'%{i}%'), Database.alternativeName.like(f'%{i}%'),
                                 Database.en_name.like(f'%{i}%')))
    query = query.order_by(Database.formula.desc())

    results: List[Database] = query.limit(20).all()
    return results


def random_film() -> Database:
    query: Query[Database] = session.query(Database)
    query = query.filter((Database.rating_kp >= 7) & (Database.votes_kp >= 50000))
    random_row = choice(query.all())
    return random_row

def get_facts(id: int) -> str:
    query = session.query(Facts).filter_by(id=id)
    facts_str = query.first().facts
    if facts_str is None:
        facts_str = ''
    return facts_str.replace('/spoiler', '/span').replace('spoiler', 'span class="tg-spoiler"')

def search_by_id(id: int) -> Database:
    query = session.query(Database).filter_by(id=id)
    result = query.first()
    return result

def get_info(line: Database) -> List[str]:
    info = []
    info.append('<b>' + (line.ru_name if line.ru_name is not None else line.alternativeName) + f'</b> <i>(id: {line.id})</i>\n')
    info.append(f'<b>Рейтинг:</b> {line.rating_kp}\n' if line.rating_kp is not None or line.rating_kp != 0 else '')
    info.append(f'<b>{line.votes_kp} оценок</b>\n' if line.votes_kp is not None or line.votes_kp != -1 else '')
    info.append(f'<b>Жанры:</b> {line.genres}\n' if line.genres is not None else '')
    info.append(f'<b>Тип материала:</b> {line.type}\n' if line.type is not None else '')
    info.append(f'<b>{line.year} год</b>\n' if line.year != -1 else '')
    info.append(f'<b>Длительность:</b> {line.movieLength} мин\n' if line.movieLength != -1 else '')
    info.append(f"<b>Рейтинг MPAA:</b> {line.ratingMpaa}\n" if line.ratingMpaa is not None else '')
    info.append(f'<b>Возрастной рейтинг</b> {line.ageRating}+\n' if line.ageRating != -1 else '')
    info.append(f'<b>Страна:</b> {line.countries}\n' if line.countries is not None else '')
    info.append(f'<b>Бюджет:</b> {line.budget_value}\n' if line.budget_value is not None else '')
    info.append(f'<b>Сборы:</b> {line.fees_world}\n' if line.fees_world is not None else '')
    info.append(f'<b>Место в топ 10:</b> {line.top10}\n' if line.top10 != -1 else '')
    info.append(f'<b>Место в топ 250:</b> {line.top250}\n' if line.top250 != -1 else '')
    info.append(f'<b>Продакшн компании:</b> {line.productionCompanies}\n' if line.productionCompanies is not None else '')
    info.append(f'<b>Актеры:</b> {line.actors}\n' if line.actors is not None else '')
    info.append(f'<b>Режиссер:</b> {line.director}\n' if line.director is not None else '')
    description = (f'<code>{line.description}</code>\n\n' if line.description is not None else '') + (
        f'<b>Коротко о фильме:</b>\n<code>{line.shortDescription}</code>\n' if line.shortDescription is not None else '')
    similar = f'<b>Похожие фильмы:</b>\n{line.similarMovies.replace("id: ", "/id_")}' if line.similarMovies is not None else ''
    trailer = line.trailer if line.trailer is not None else ''
    short = ''.join(info[0:2])+info[5]+ info[3] + info[9] + info[16]
    sequels = f'<b>Сиквелы и приквелы:</b>\n{line.sequelsAndPrequels.replace("id: ", "/id_")}\n' if line.sequelsAndPrequels is not None else ''
    return [short, description, similar, trailer, ''.join(info), sequels]


def filter_database(database: session, filters: Dict[str, str | bool]) -> List[Database]:
    query: Query[Database] = database.query(Database)

    filter_key: str
    filter_value: str | int | float | bool
    for filter_key, filter_value in filters.items():
        match filter_key:
            case 'top10':
                if filter_value: query = query.filter(Database.top10 != -1)
            case 'top250':
                if filter_value: query = query.filter(Database.top250 != -1)
            case 'director':
                filter_value = filter_value.strip()
                query = query.filter(Database.director.like(f'%{filter_value}%'))
            case 'actors':
                query = query.filter(Database.actors.like(f'%{filter_value}%'))
            case 'name':
                lst = filter_value.replace(',', '').split()
                for i in lst:
                    query = query.filter(Database.ru_name.like(f'%{i}%'))
            case 'year':
                filter_value = filter_value.replace(' ', '')
                if '-' in filter_value:
                    mn = int(filter_value[:filter_value.find('-')])
                    mx = int(filter_value[filter_value.find('-') + 1:])
                    year_filter = (Database.year >= mn) & (Database.year <= mx)
                else:
                    mn = int(filter_value)
                    year_filter = (Database.year >= mn)
                query = query.filter(year_filter)
            case 'genres':
                lst = filter_value.replace(',', '').split()
                for i in lst:
                    query = query.filter(Database.genres.like(f'%{i}%'))
            case 'rating_kp':
                filter_value = filter_value.replace(' ', '')
                if '-' in filter_value:
                    mn = float(filter_value[:filter_value.find('-')])
                    mx = float(filter_value[filter_value.find('-') + 1:])
                    rating_filter = (Database.rating_kp >= mn) & (Database.rating_kp <= mx)
                else:
                    mn = float(filter_value)
                    rating_filter = (Database.rating_kp >= mn)
                query = query.filter(rating_filter)
            case 'votes_kp':
                filter_value = filter_value.replace(' ', '')
                if '-' in filter_value:
                    mn = float(filter_value[:filter_value.find('-')])
                    mx = float(filter_value[filter_value.find('-') + 1:])
                    rating_filter = (Database.votes_kp >= mn) & (Database.votes_kp <= mx)
                else:
                    mn = float(filter_value)
                    rating_filter = (Database.votes_kp >= mn)
                query = query.filter(rating_filter)
            case 'productionCompanies':
                lst = filter_value.replace(',', ' ').strip().split()
                for i in lst:
                    query = query.filter(Database.productionCompanies.like(f'%{i}%'))

            case 'type':
                query = query.filter(Database.type.like(f'%{filter_value}%'))
            case 'ratingMpaa':
                query = query.filter(Database.ratingMpaa.like(f'%{filter_value}%'))

        # Добавьте другие условия фильтрации по необходимости

    query = query.order_by(Database.rating_kp.desc())
    res: List[Database] = query.limit(100).all()

    return res


filters: Dict[str, str | bool] = {
    'name': 'Барби',
    'genres': 'для взрослых',
    'rating_kp': '7.0',
    'year': ' 2000',
    'director': ' тарантино      ',
    'actors': 'Дикаприо',
    'type': 'tv-series',
    'top10': True,
    'top250': True,
    'productionCompanies': 'Marvel Studios',
    'votes_kp': '20000',
    'ratingMpaa': 'nc17'
}


# results = filter_database(session, filters)
# results = search_name(session, 'барби')
# row: Dict[str, Any]
# for row in results:
#     name = row.ru_name if row.ru_name is not None else row.alternativeName
#     l = len(row.ru_name) if row.ru_name is not None else len(row.alternativeName)
#     print(f'{name + " " * (25 - l)}|| {row.id} | {row.genres} | {row.rating_kp} | {row.year} | {row.votes_kp}')

def print_row(line: Database):
    name = line.ru_name if line.ru_name is not None else line.alternativeName
    print(name)
    print(f'Рейтинг: {line.rating_kp}') if line.rating_kp is not None or line.rating_kp != 0 else None
    print(f'{line.votes_kp} оценок') if line.votes_kp is not None or line.votes_kp != -1 else None
    print(f'Жанры: {line.genres}') if line.genres is not None else None
    print(line.type) if line.type is not None else None
    print(f'{line.year} год') if line.year != -1 else None
    print(f'Длительность: {line.movieLength} мин') if line.movieLength != -1 else None
    print(f"Рейтинг MPAA: {line.ratingMpaa}") if line.movieLength is not None else None
    print(f'Возрастной рейтинг {line.ageRating}+') if line.ageRating != -1 else None
    print(f'Страна-производитель: {line.countries}') if line.countries is not None else None
    print(f'Бюджет: {line.budget_value}') if line.budget_value is not None else None
    print(f'Сборы: {line.fees_world}') if line.fees_world is not None else None
    print(f'Место в топ 10:{line.top10}') if line.top10 != -1 else None
    print(f'Место в топ 250: {line.top250}') if line.top250 != -1 else None
    print(f'Продакшн компании: {line.productionCompanies}') if line.productionCompanies is not None else None
    print(f'Трейлер: {line.trailer}') if line.trailer is not None else None
    print(f'Похожие фильмы:\n{line.similarMovies}\n') if line.similarMovies is not None else None
    print(f'Сиквелы и приквелы: {line.sequelsAndPrequels}\n') if line.sequelsAndPrequels is not None else None
    print(f'Актеры: {line.actors}') if line.actors is not None else None
    print(f'Режиссер: {line.director}') if line.director is not None else None
    print(f'Описание: {line.description}') if line.description is not None else None
    print(f'Коротко о фильме: {line.shortDescription}') if line.shortDescription is not None else None


def open_film(data: List[Database], ind: bool = True) -> None:
    if ind:
        print('Чтобы открыть полную информацию о фильме, введите номер фильма. Чтобы выбрать новый фильм, нажмите 0')
    ans = int(input())
    if ans == 0:
        __main__()
    elif ans > len(data):
        print('Вы ввели неправильный номер. Попрубуйте еще раз или нажмите ноль, чтобы выйти')
        open_film(data, False)
    else:
        row = data[ans - 1]
        print_row(row)
        print()
        print('Введите номер другого фильма, чтобы открыть полную информацию о фильме:')
        cnt = 0
        for i in data:
            cnt += 1
            name = i.ru_name if i.ru_name is not None else i.alternativeName
            print(f'{cnt}. {name}. ', end=' ')
        print('\n', end='')
        open_film(data, False)


def __main__() -> None:
    print('0: Поиск по названию')
    print('1: Фильтр фильмов')
    print('2: Рандомный фильм')
    answer = input()
    match answer:
        case '0':
            result = search_name(session, input('Введите название фильма/сериала:\n'))
            if len(result) < 1:
                print('Ничего не нашлось((\nПопрубуйте еще раз')
                __main__()
                exit()
            cnt = 0
            for row in result:
                cnt += 1
                name = row.ru_name if row.ru_name is not None else row.alternativeName
                l = len(row.ru_name) if row.ru_name is not None else len(row.alternativeName)
                print(f'{cnt}. {name} || рейтинг КП: {row.rating_kp} | {row.votes_kp} оценок | {row.year} год')
            open_film(result)

        case '1':
            filt = ['name', 'genres', 'rating_kp', 'year', 'director', 'actors', 'type', 'top10', 'top250',
                    'productionCompanies', 'votes_kp', 'ratingMpaa']
            filt_dict = {}
            for i in range(1, len(filt) + 1):
                print(f'{i}. {filt[i - 1]}')
            ans = 1
            while True:
                print('Введите номер нужного фильтра. Чтобы найти фильм по введеным фильтрам, нажмите 0')
                try:
                    ans = int(input())
                except Exception:
                    print('Вы ввели неправильную команду')
                    continue
                if ans == 0:
                    if len(filt_dict) == 0:
                        print('Вы не ввели ни одного фильтра')
                        continue
                    else:
                        break
                filt_dict[filt[ans - 1]] = input(f'Введите фильтр по значению {filt[ans - 1]}: ')
            data = filter_database(session, filt_dict)
            if len(data) < 1:
                print('Ничего не нашлось((\nПопробуйте еще раз')
                __main__()
                exit()
            cnt = 0
            for row in data:
                cnt += 1
                name = row.ru_name if row.ru_name is not None else row.alternativeName
                l = len(row.ru_name) if row.ru_name is not None else len(row.alternativeName)
                print(f'{cnt}. {name} || рейтинг КП: {row.rating_kp} | {row.votes_kp} оценок | {row.year} год')
            open_film(data)
        case '2':
            result = random_film()
            print_row(result)
            __main__()
        case _:
            print('Вы ввели неправильную команду')
            __main__()


if __name__ == '__main__':
    __main__()
