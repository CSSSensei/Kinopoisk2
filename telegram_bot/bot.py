from aiogram import Bot
from aiogram.client.default import DefaultBotProperties

from telegram_bot.config import config

bot = Bot(token=config.token, default=DefaultBotProperties(parse_mode="HTML"))
