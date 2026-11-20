from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from telegram_bot import phrases
from telegram_bot.handlers.callbacks_data import FactsCallBack, MovieCallBack, SectionPage
from telegram_bot.presenters import LABELS, Section


keyboard = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=phrases.FIND)], [KeyboardButton(text=phrases.RANDOM)]],
                               resize_keyboard=True)


def button(title, data):
    return InlineKeyboardButton(text=title, callback_data=data.pack())


def movie_keyboard(media_id, available, section=Section.CARD, page=0, total=1):
    rows = []
    if total > 1:
        nav = []
        for target, label in ((page - 1, "‹"), (page + 1, "›")):
            if 0 <= target < total:
                data = SectionPage(movie_id=media_id, action=section, page=target)
                nav.append(button(label, data))
        rows.append(nav)
    if section == Section.CARD:
        buttons = []
        for action, title in LABELS.items():
            if action in available:
                data = (FactsCallBack(movie_id=media_id, page=0) if action == Section.FACTS else
                        MovieCallBack(movie_id=media_id, action=action))
                buttons.append(button(title, data))
        rows.extend(buttons[i:i+2] for i in range(0, len(buttons), 2))
    else:
        rows.append([button("Назад", MovieCallBack(movie_id=media_id, action=Section.CARD))])
    return InlineKeyboardMarkup(inline_keyboard=rows)
