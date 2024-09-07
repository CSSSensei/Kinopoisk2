from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardRemove

from DB.movie_DB import search_en_name, random_film, get_info  # TODO переименовать это говно
from aiogram import Router, F

from states.states import SearchMovie
from keyboards import user_keyboards
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import draft

router = Router()
engine = create_engine('mysql+pymysql://root:root@localhost:3306/new_schema')
Session = sessionmaker(bind=engine)
session = Session()


@router.message(F.text == 'Найти фильм')
async def process_insert_film_name(message: Message, state: FSMContext):
    await message.answer(text='Введите название фильма', reply_markup=ReplyKeyboardRemove())
    await state.set_state(SearchMovie.insert_film_name)


@router.message(F.text == 'Рандомный фильм', ~StateFilter(SearchMovie.insert_film_name))
async def process_random_film(message: Message):
    line = random_film()
    link = f'https://st.kp.yandex.net/images/film_big/{line.id}.jpg'
    txt = get_info(line)
    if len(txt[5]) == 0:
        await message.answer_photo(photo=link, caption=txt[0], reply_markup=user_keyboards.movie_keyboard(line))
    else:
        await message.answer_photo(photo=link, caption=txt[0], reply_markup=user_keyboards.movie_keyboard(line))
        

@router.message(StateFilter(SearchMovie.insert_film_name))
async def return_film_info(message: Message, state: FSMContext):
    text = message.text
    films = []
    if text != '':
        films = search_en_name(text)

    flag = True
    if text != '' and len(films) == 0:
        await message.answer('Фильмов не найдено', reply_markup=user_keyboards.keyboard)
        await state.clear()
    else:
        lst = ''
        for i in films:
            if flag:
                flag = False
                id = i.id
                link = f'https://st.kp.yandex.net/images/film_big/{id}.jpg'
            if i.ru_name:
                lst += i.ru_name
            else:
                lst += i.alternativeName
            lst += f' ({i.year}, рейтинг КП: {i.rating_kp})   <i>/id_{i.id}</i>\n'
        if not flag:
            await message.answer_photo(photo=link)
        await message.answer(lst, reply_markup=user_keyboards.keyboard)
        await state.clear()


@router.message(lambda message: message.text.lower() == 'спасибо' or message.text.lower() == 'от души' or message.text.lower() == 'благодарю')
async def u_r_wellcome(message: Message):
    await message.answer_sticker(sticker='CAACAgEAAxkBAAEKShplAfTsN4pzL4pB_yuGKGksXz2oywACZQEAAnY3dj9hlcwZRAnaOjAE')


@router.message()
async def process_name_command(message: Message):
    await message.answer(text='К сожалению, я не понимаю, о чем вы', reply_markup=user_keyboards.keyboard)
