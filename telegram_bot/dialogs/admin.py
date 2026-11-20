from zoneinfo import ZoneInfo

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.formatting import Text

from telegram_bot.handlers.callbacks_data import CutMessageCallBack, HistoryChunk
from telegram_bot.keyboards.user_keyboards import button
from telegram_bot.presenters import pages


MOSCOW = ZoneInfo("Europe/Moscow")
USERS_PER_PAGE = 12


def query_line(row):
    who = f"@{row['username']}" if row['username'] else str(row['user_id'])
    date = row["query_date"].astimezone(MOSCOW)
    return f"{who} — [{date:%d.%m.%Y %H:%M:%S}]\n{row['query_text']}"


async def admin_page(users, action, user_id, page, chunk=0):
    if page < 1 or page > 2**31-1 or not 0 <= user_id < 2**63:
        return None
    nav, chunks = [], []
    if action == 1:
        total, rows = await users.users((page-1)*USERS_PER_PAGE, USERS_PER_PAGE)
        if not rows and page > 1:
            return None
        lines = [f"Всего пользователей: {total}"]
        for row in rows:
            name = row['username'] or str(row['user_id'])
            date = row['registration_date'].astimezone(MOSCOW)
            lines.append(f"{name} | {row['user_id']} | {'👑 ' if row['is_admin'] else ''}{row['queries']} [{date:%d.%m.%Y}]")
        chunks = pages(Text("\n".join(lines)), 4096)
        has_next = page*USERS_PER_PAGE < total
    elif action == 2 and user_id:
        rows = await users.queries(page-1, 2, user_id)
        if not rows:
            return None
        chunks = pages(Text("История запросов\n", query_line(rows[0])), 4096)
        has_next = len(rows) > 1
    else:
        return None
    if not 0 <= chunk < len(chunks):
        return None
    for target, label in ((page-1, "‹"), (page+1, "›")):
        if target >= 1 and (target < page or has_next):
            nav.append(button(label, CutMessageCallBack(action=action, user_id=user_id, page=target)))
    rows = [nav] if nav else []
    if len(chunks) > 1:
        rows.append([button(label, HistoryChunk(user_id=user_id, page=page, chunk=target))
                     for target, label in ((chunk-1, "Предыдущая часть"), (chunk+1, "Следующая часть"))
                     if 0 <= target < len(chunks)])
    return chunks[chunk], InlineKeyboardMarkup(inline_keyboard=rows) if rows else None
