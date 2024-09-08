from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardRemove

from DB.movie_DB import search_en_name, random_film, get_info
from aiogram import Router, F

from config_data.models import Movie
from filters.UCommands import get_link
from states.states import SearchMovie
from keyboards import user_keyboards

router = Router()


@router.message(F.text == 'Найти фильм')
async def process_insert_film_name(message: Message, state: FSMContext):
    await message.answer(text='Введите название фильма', reply_markup=ReplyKeyboardRemove())
    await state.set_state(SearchMovie.insert_film_name)


@router.message(F.text == 'Рандомный фильм', ~StateFilter(SearchMovie.insert_film_name))
async def process_random_film(message: Message):
    line: Movie = random_film()
    if line is None:
        await message.answer('Произошла ошибка((')
        return
    link = get_link(line.id)
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
        link = ''
        for i in films:
            if flag:
                flag = False
                id = i.id
                link = get_link(id)
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
