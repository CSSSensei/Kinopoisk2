from zoneinfo import ZoneInfo

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.formatting import BlockQuote, Bold, Code, Italic, Strikethrough, Text, TextLink

from telegram_bot.handlers.callbacks_data import AdminPage
from telegram_bot.keyboards.user_keyboards import button
from telegram_bot.presenters import pages

MOSCOW = ZoneInfo("Europe/Moscow")
USERS_PER_PAGE = 15
QUERIES_PER_PAGE = 6


def mention(user):
    label = f"@{user['username']}" if user["username"] else user["first_name"] or user["last_name"] or str(user["user_id"])
    return TextLink(label, url=f"tg://user?id={user['user_id']}")


def user_list(rows, total):
    lines = [Bold("Пользователи"), "\n", Italic(f"{total} всего"), "\n\n"]
    for row in rows:
        count = row["queries"]
        icon = next((icon for threshold, icon in ((100, "🤯"), (50, "🔥"), (10, "😮"), (5, "😎"))
                     if count > threshold), "🐥")
        date = row["registration_date"].astimezone(MOSCOW)
        detail = Text(mention(row), "  ", Italic(f"{date:%d.%m.%Y}"), f" {icon} {count}")
        if row["is_banned"]:
            detail = Strikethrough(detail)
        elif row["is_admin"]:
            detail = Bold(detail)
        lines.extend((Code(str(row["user_id"]).ljust(12)), detail, "\n"))
    if total > USERS_PER_PAGE:
        lines.extend(Text(Code("."), "\n") for _ in range(USERS_PER_PAGE - len(rows)))
    return Text(*lines)


def query_list(rows, user=None):
    lines = [Bold("Запросы")]
    if user is not None:
        lines.extend(("\n", Italic("пользователя ", mention(user))))
    lines.append("\n\n")
    for row in rows:
        if user is None:
            lines.extend((mention(row), " "))
        date = row["query_date"].astimezone(MOSCOW)
        lines.extend((BlockQuote(f"{date:%d.%m.%Y %H:%M:%S}"), " ", Italic(row["query_text"]), "\n\n"))
    return Text(*lines)


def navigation(cursor, total_pages, parts):
    page = cursor.page
    rows = []
    if total_pages > 1:
        def target(label, dest):
            if dest is None:
                return InlineKeyboardButton(text=label, callback_data="admin:noop")
            return button(label, cursor.model_copy(update={"page": dest, "part": 0}))

        rows.append([
            target("« 1", 1) if page > 1 else target(" ", None),
            target("❮", page - 1) if page > 1 else target(" ", None),
            target(str(page), None),
            target("❯", page + 1) if page < total_pages else target(" ", None),
            target(f"{total_pages} »", total_pages) if page < total_pages else target(" ", None),
        ])
    if parts > 1:
        rows.append([button(label, cursor.model_copy(update={"part": part}))
                     for label, part in (("❮ часть", cursor.part - 1), ("часть ❯", cursor.part + 1))
                     if 0 <= part < parts])
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


async def admin_page(users, cursor: AdminPage):
    if not 1 <= cursor.page <= 2**31-1 or not 0 <= cursor.user_id < 2**63:
        return None
    if cursor.view == "users":
        per_page = USERS_PER_PAGE
        total, rows = await users.users((cursor.page - 1) * per_page, per_page)
        content = user_list(rows, total)
    else:
        per_page = QUERIES_PER_PAGE
        rows = await users.queries((cursor.page - 1) * per_page, per_page, cursor.user_id)
        if not rows:
            return None
        total = await users.count_queries(cursor.user_id)
        content = query_list(rows, rows[0])
    total_pages = max(1, (total + per_page - 1) // per_page)
    if cursor.page > total_pages:
        return None
    chunks = pages(content, 4096)
    if not 0 <= cursor.part < len(chunks):
        return None
    return chunks[cursor.part], navigation(cursor, total_pages, len(chunks))
