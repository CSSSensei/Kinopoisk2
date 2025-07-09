from aiogram import Router
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import default_state
from aiogram.types import Message


from filters.UCommands import get_link
from filters.filters import CheckId
from keyboards import user_keyboards
from DB.movie_interface import AbstractMovieDB
from config_data.config import Config, load_config
from DB.db_factory import DBFactory
from lexicon.lexicon import LEXICON_RU

router = Router()
config: Config = load_config()
db_instance: AbstractMovieDB = DBFactory.get_db_instance(config)

# TODO сделать lexicon файл


@router.message(CheckId())  # /id_...
async def search(message: Message):
    s = message.text[4:]
    movie_id = int(s)
    line = db_instance.search_by_id(movie_id)
    if line is not None:
        txt = db_instance.get_info(line)
        link = get_link(movie_id)
        await message.answer_photo(photo=link, caption=txt[0], reply_markup=user_keyboards.movie_keyboard(line))

    else:
        await message.answer('Такого id не существует', reply_markup=user_keyboards.keyboard)


@router.message(CommandStart())  # /start
async def process_start_command(message: Message):
    await message.answer(LEXICON_RU['/start'], reply_markup=user_keyboards.keyboard)


@router.message(Command(commands='cancel'), StateFilter(default_state))   # /cancel
async def process_cancel_command(message: Message):
    await message.answer(text=LEXICON_RU['/cancel'], reply_markup=user_keyboards.keyboard)


@router.message(Command(commands='cancel'), ~StateFilter(default_state))   # /cancel
async def process_cancel_command_state(message: Message, state: FSMContext):
    await message.answer(text=LEXICON_RU['/cancel_movie'], reply_markup=user_keyboards.keyboard)
    await state.clear()


@router.message(Command(commands=['help']))  # /help
async def process_help_command(message: Message):
    await message.answer(LEXICON_RU['/help'], reply_markup=user_keyboards.keyboard)


@router.message(Command(commands=['about']))  # /help
async def process_help_command(message: Message):
    await message.answer(LEXICON_RU['/about'], reply_markup=user_keyboards.keyboard)
