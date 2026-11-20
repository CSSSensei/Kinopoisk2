from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.formatting import Text
from aiogram_dialog import Dialog, DialogManager, Window
from aiogram_dialog.widgets.link_preview import LinkPreview
from aiogram_dialog.widgets.text import Format

from telegram_bot.lexicon import phrase
from telegram_bot.dialogs.pagination import page_index, pager
from telegram_bot.presenters.admin import USERS_PER_PAGE, query_list, user_list
from telegram_bot.presenters.pagination import pages

QUERIES_PER_PAGE = 6


class AdminList(StatesGroup):
    users = State()
    queries = State()


async def reset_part(event, widget, manager):
    await manager.find("part").set_page(0)


async def list_data(dialog_manager: DialogManager, users, **kwargs):
    actor = dialog_manager.event.from_user
    if not await users.is_admin(actor.id):
        return {"text": phrase("error.access"), "rows_count": 1, "part_count": 1}

    if dialog_manager.current_context().state == AdminList.users:
        index = max(0, min(await dialog_manager.find("rows").get_page(), 2**31 - 1))
        total, rows = await users.users(index * USERS_PER_PAGE, USERS_PER_PAGE)
        count = max(1, (total + USERS_PER_PAGE - 1) // USERS_PER_PAGE)
        bounded = await page_index(dialog_manager, "rows", count)
        if bounded != index:
            _, rows = await users.users(bounded * USERS_PER_PAGE, USERS_PER_PAGE)
        content = user_list(rows, total)
    else:
        user_id = dialog_manager.start_data["user_id"]
        total = await users.count_queries(user_id)
        count = max(1, (total + QUERIES_PER_PAGE - 1) // QUERIES_PER_PAGE)
        index = await page_index(dialog_manager, "rows", count)
        rows = await users.queries(index * QUERIES_PER_PAGE, QUERIES_PER_PAGE, user_id)
        content = query_list(rows, rows[0]) if rows else Text(phrase("error.no_history"))
    chunks = pages(content, 4096)
    part = await page_index(dialog_manager, "part", len(chunks))
    return {"text": chunks[part].as_html(), "rows_count": count, "part_count": len(chunks)}


def admin_dialog():
    return Dialog(*(Window(
        Format("{text}"), pager("rows", on_change=reset_part), pager("part", current=phrase("buttons.current_part")),
        LinkPreview(is_disabled=True), getter=list_data, state=state, parse_mode="HTML",
    ) for state in (AdminList.users, AdminList.queries)))
