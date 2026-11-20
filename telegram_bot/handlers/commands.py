from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from telegram_bot.lexicon import phrase
from telegram_bot.handlers.admin_commands import command_menu
from telegram_bot.keyboards.user_keyboards import keyboard


async def start(message: Message):
    await message.answer(phrase("commands.start"), reply_markup=keyboard)


async def help_command(message: Message):
    await message.answer(phrase("commands.help"), reply_markup=keyboard)


async def commands(message: Message):
    await message.answer(**command_menu(admin=False).as_kwargs())


async def about(message: Message):
    await message.answer(phrase("commands.about"), reply_markup=keyboard)


async def cancel(message: Message, state: FSMContext):
    active = await state.get_state()
    await state.clear()
    await message.answer(phrase("commands.canceled") if active else phrase("commands.inactive"), reply_markup=keyboard)


def router():
    result = Router(name="commands")
    result.message.register(start, CommandStart())
    result.message.register(help_command, Command("help"))
    result.message.register(about, Command("about"))
    result.message.register(commands, Command("commands", "cmds", ignore_case=True))
    result.message.register(cancel, Command("cancel"))
    return result
