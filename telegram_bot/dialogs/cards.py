from aiogram import F
from aiogram.enums import ContentType
from aiogram.fsm.state import State, StatesGroup
from aiogram_dialog import Dialog, DialogManager, Window
from aiogram_dialog.api.entities import MediaAttachment
from aiogram_dialog.widgets.kbd import Button, Group
from aiogram_dialog.widgets.media import DynamicMedia
from aiogram_dialog.widgets.text import Const, Format

from telegram_bot.dialogs.pagination import page_index, pager
from telegram_bot.lexicon import phrase
from telegram_bot.presenters import LABELS, Section, pages, sections


class MovieCard(StatesGroup):
    view = State()


async def select_section(callback, button, manager):
    manager.dialog_data["section"] = button.widget_id
    await manager.find("page").set_page(0)


async def card_data(dialog_manager: DialogManager, catalog, **kwargs):
    card = dialog_manager.middleware_data.get("opening_card") or await catalog.card(dialog_manager.start_data["media_id"])
    if card is None:
        return {"text": phrase("catalog.missing"), "poster": None, "page_count": 1, "available": [], "back": False}
    content = sections(card)
    section = Section(dialog_manager.dialog_data.get("section", Section.CARD))
    if section not in content:
        section = Section.CARD
    poster = None if dialog_manager.dialog_data.get("text_only") else dialog_manager.start_data["poster"]
    chunks = pages(content[section], 1024 if poster else 4096)
    index = await page_index(dialog_manager, "page", len(chunks))
    return {
        "text": chunks[index].as_html(), "page_count": len(chunks),
        "poster": MediaAttachment(ContentType.PHOTO, url=poster) if poster else None,
        "available": list(content) if section == Section.CARD else [],
        "back": section != Section.CARD,
    }


def card_dialog():
    return Dialog(Window(
        Format("{text}"), DynamicMedia("poster"), pager("page"),
        Group(*(Button(Const(title), id=section.value, on_click=select_section,
                       when=F["available"].contains(section)) for section, title in LABELS.items()), width=2),
        Button(Const(phrase("buttons.back")), id=Section.CARD.value, on_click=select_section, when="back"),
        state=MovieCard.view, getter=card_data, parse_mode="HTML",
    ))
