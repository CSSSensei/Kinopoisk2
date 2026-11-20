from zoneinfo import ZoneInfo

from aiogram.utils.formatting import BlockQuote, Bold, Code, Italic, Strikethrough, Text, TextLink

from telegram_bot.lexicon import phrase, rich_phrase


MOSCOW = ZoneInfo("Europe/Moscow")
USERS_PER_PAGE = 15


def mention(user):
    label = f"@{user['username']}" if user["username"] else user["first_name"] or user["last_name"] or str(user["user_id"])
    return TextLink(label, url=f"tg://user?id={user['user_id']}")


def user_list(rows, total):
    lines = [Bold(phrase("admin.users")), "\n", Italic(phrase("admin.total").format(total=total)), "\n\n"]
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
    lines = [Bold(phrase("admin.queries"))]
    if user is not None:
        lines.extend(("\n", Italic(rich_phrase("admin.user_history", user=mention(user)))))
    lines.append("\n\n")
    for row in rows:
        if user is None:
            lines.extend((mention(row), " "))
        date = row["query_date"].astimezone(MOSCOW)
        lines.extend((BlockQuote(f"{date:%d.%m.%Y %H:%M:%S}"), " ", Italic(row["query_text"]), "\n\n"))
    return Text(*lines)
