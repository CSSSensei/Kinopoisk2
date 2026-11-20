from aiogram.utils.formatting import Bold, Italic, Text

from telegram_bot.lexicon import phrase

ADMIN_COMMANDS = {
    ("users", "u"): phrase("admin_commands.users"),
    ("commands", "cmds"): phrase("admin_commands.commands"),
    ("ban",): phrase("admin_commands.ban"),
    ("unban",): phrase("admin_commands.unban"),
    ("promote",): phrase("admin_commands.promote"),
    ("demote",): phrase("admin_commands.demote"),
    ("query", "q"): phrase("admin_commands.query"),
    ("clear_temp",): phrase("admin_commands.clear_temp"),
    ("user_query", "uq", "qu"): phrase("admin_commands.user_query"),
    ("test",): phrase("admin_commands.test"),
}

USER_COMMANDS = {
    ("start",): phrase("user_commands.start"),
    ("help",): phrase("user_commands.help"),
    ("about",): phrase("user_commands.about"),
    ("cancel",): phrase("user_commands.cancel"),
    ("commands", "cmds"): phrase("user_commands.commands"),
}
ADMIN_NAMES = {name for aliases in ADMIN_COMMANDS for name in aliases}


def command_list(commands):
    return "\n".join(
        ", ".join(f"/{alias}" for alias in aliases)
        + (" " if description.startswith("{") else " — ") + description
        for aliases, description in commands.items()
    )


def command_menu(admin):
    title = Bold(phrase("menu.title"))
    public = command_list(USER_COMMANDS)
    if not admin:
        return Text(title, "\n\n", public)
    return Text(title, "\n\n", Italic(phrase("menu.admin")), "\n", command_list(ADMIN_COMMANDS),
                "\n\n", Italic(phrase("menu.user")), "\n", public)
