from aiogram import Bot
from aiogram.client.default import DefaultBotProperties

from config_data.config import config

bot = Bot(token=config.tg_bot.token, default=DefaultBotProperties(parse_mode="HTML"))
