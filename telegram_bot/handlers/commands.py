from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from telegram_bot import phrases
from telegram_bot.keyboards.user_keyboards import keyboard


async def start(message: Message):
    await message.answer(phrases.START, reply_markup=keyboard)


async def help_command(message: Message):
    await message.answer(phrases.HELP, reply_markup=keyboard)


async def about(message: Message):
    await message.answer(phrases.ABOUT, reply_markup=keyboard)


async def cancel(message: Message, state: FSMContext):
    active = await state.get_state()
    await state.clear()
    await message.answer("Поиск отменён." if active else "Сейчас нет активного поиска.", reply_markup=keyboard)


def router():
    result = Router(name="commands")
    result.message.register(start, CommandStart())
    result.message.register(help_command, Command("help"))
    result.message.register(about, Command("about"))
    result.message.register(cancel, Command("cancel"))
    return result
