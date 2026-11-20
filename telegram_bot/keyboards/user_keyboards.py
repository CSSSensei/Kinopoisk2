from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from telegram_bot.lexicon import phrase


keyboard = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=phrase("buttons.find"))], [KeyboardButton(text=phrase("buttons.random"))]],
                               resize_keyboard=True)
