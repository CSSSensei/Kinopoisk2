from aiogram.utils.formatting import Bold, Italic, Text

ADMIN_COMMANDS = {
    ("users", "u"): "таблица со всеми пользователями",
    ("commands", "cmds"): "список всех доступных команд",
    ("ban",): "{user_id} — заблокировать пользователя по ID",
    ("unban",): "{user_id} — разблокировать пользователя по ID",
    ("promote",): "{user_id} — повысить уровень доступа",
    ("demote",): "{user_id} — понизить уровень доступа",
    ("query", "q"): "{N} — последние N запросов",
    ("clear_temp",): "очистка временных файлов",
    ("user_query", "uq", "qu"): "{user_id} — запросы пользователя по ID",
    ("test",): "отладка и тестирование функций",
}

USER_COMMANDS = {
    ("start",): "запустить бота",
    ("help",): "как пользоваться ботом",
    ("about",): "о боте",
    ("cancel",): "завершить поиск",
    ("commands", "cmds"): "список всех команд (это сообщение)",
}
ADMIN_NAMES = {name for aliases in ADMIN_COMMANDS for name in aliases}


def command_list(commands):
    return "\n".join(
        ", ".join(f"/{alias}" for alias in aliases)
        + (" " if description.startswith("{") else " — ") + description
        for aliases, description in commands.items()
    )


def command_menu(admin):
    title = Bold("Доступные команды")
    public = command_list(USER_COMMANDS)
    if not admin:
        return Text(title, "\n\n", public)
    return Text(title, "\n\n", Italic("Админские"), "\n", command_list(ADMIN_COMMANDS),
                "\n\n", Italic("Пользовательские"), "\n", public)
