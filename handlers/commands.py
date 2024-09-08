from aiogram import Router
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import default_state
from aiogram.types import Message

from DB.movie_DB import search_by_id, get_info
from filters.UCommands import get_link
from filters.filters import CheckId
from keyboards import user_keyboards

router = Router()


@router.message(CheckId())  # /id_...
async def search(message: Message):
    s = message.text[4:]
    movie_id = int(s)
    line = search_by_id(movie_id)
    if line is not None:
        txt = get_info(line)
        link = get_link(movie_id)
        await message.answer_photo(photo=link, caption=txt[0], reply_markup=user_keyboards.movie_keyboard(line))

    else:
        await message.answer('Такого id не существует', reply_markup=user_keyboards.keyboard)


@router.message(CommandStart())  # /start
async def process_start_command(message: Message):
    await message.answer('Привет!\nМеня зовут CineBot!\nНапиши /help чтобы узнать, как пользоваться ботом',
                         reply_markup=user_keyboards.keyboard)


@router.message(Command(commands='cancel'), StateFilter(default_state))   # /cancel
async def process_cancel_command(message: Message):
    await message.answer(text='Отменять нечего', reply_markup=user_keyboards.keyboard)


@router.message(Command(commands='cancel'), ~StateFilter(default_state))   # /cancel
async def process_cancel_command_state(message: Message, state: FSMContext):
    await message.answer(text='Вы вышли из поиска фильмов', reply_markup=user_keyboards.keyboard)
    await state.clear()


@router.message(Command(commands=['help']))  # /help
async def process_help_command(message: Message):
    await message.answer(
        '🌟 Лови горячие команды для поиска фильмов и сериалов! 🎬🔎\n'
        '✨ /id_xxxx: используй эту команду, чтобы мгновенно найти фильм или сериал по уникальному идентификатору.\n'
        '💫 "Найти фильм": просто введи название фильма или сериала, и я помогу найти его. Не беспокойся о регистре, но старайся соблюдать орфографию, чтобы результат был точным. Если что, посмотри правильное название на Кинопоиске.\n'
        '🌟 "Рандомный фильм": дай мне шанс удивить тебя! Я найду случайный фильм с рейтингом не менее 7.0 на КиноПоиске и с количеством оценок не меньше 50 тысяч. Подготовься к незабываемому просмотру! 🍿🎉',
        reply_markup=user_keyboards.keyboard)
