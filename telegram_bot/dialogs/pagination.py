from aiogram import F
from aiogram_dialog.widgets.kbd import CurrentPage, FirstPage, LastPage, NextPage, PrevPage, Row, StubScroll
from aiogram_dialog.widgets.text import Case, Const, Format

from telegram_bot.lexicon import phrase


def pager(name, *, on_change=None, current="{current_page1}"):
    count = f"{name}_count"

    def label(key, condition):
        return Case({True: Format(phrase(key)), False: Const(" ")}, condition)

    return Row(
        StubScroll(name, pages=count, on_page_changed=on_change),
        FirstPage(name, id=f"{name}_nav", text=label("buttons.first", F["current_page"] > 0)),
        PrevPage(name, id=f"{name}_nav", text=label("buttons.prev", F["current_page"] > 0)),
        CurrentPage(name, id=f"{name}_nav", text=Format(current)),
        NextPage(name, id=f"{name}_nav", text=label("buttons.next", F["current_page1"] < F["pages"])),
        LastPage(name, id=f"{name}_nav", text=label("buttons.last", F["current_page1"] < F["pages"])),
        when=F[count] > 1,
    )


async def page_index(manager, name, count):
    scroll = manager.find(name)
    current = await scroll.get_page()
    bounded = max(0, min(current, count - 1))
    if current != bounded:
        await scroll.set_page(bounded)
    return bounded
