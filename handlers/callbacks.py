from typing import Union, Tuple

from aiogram import Router, F
from aiogram.filters.callback_data import CallbackData
from aiogram.types import CallbackQuery
from config_data.config import Config, load_config

from keyboards import user_keyboards
from DB.movie_DB import get_info, get_facts, search_by_id
from filters.UCommands import get_id, cut_back, split_text

router = Router()

config: Config = load_config()


class MovieCallBack(CallbackData, prefix="movie"):
    movie_id: int
    action: int


class FactsCallBack(CallbackData, prefix="fact"):
    movie_id: int
    page: int
    action: int = 0


@router.callback_query(MovieCallBack.filter())
async def moderate_film_callbacks(callback: CallbackQuery, callback_data: MovieCallBack):
    action = callback_data.action
    movie_id = callback_data.movie_id
    movie = search_by_id(movie_id)

    action_to_index = {
        -1: 0,
        0: 1,
        1: 3,
        2: 2,
        3: 5,
        4: 4,
    }

    index = action_to_index.get(action, -1)
    await callback.message.edit_caption(
        caption=get_info(movie)[index],
        reply_markup=user_keyboards.movie_keyboard(movie, action != -1)
    )


@router.callback_query(FactsCallBack.filter())
async def moderate_film_callbacks(callback: CallbackQuery, callback_data: FactsCallBack):
    page = callback_data.page
    action = callback_data.action
    if action == -2:
        await callback.answer(str(page + 1))
        return
    movie_id = callback_data.movie_id

    facts, max_page = _get_facts_by_page(movie_id, page)
    await callback.message.edit_caption(
        caption=facts,
        reply_markup=user_keyboards.facts_keyboard(movie_id, page, max_page=max_page)
    )


@router.callback_query(F.data == 'button_00_pressed')
async def process_button_1_press(callback: CallbackQuery):
    id = get_id(callback.message.caption)
    txt = get_info(search_by_id(id))
    if len(txt[5]) == 0:
        await callback.message.edit_caption(caption=txt[0], reply_markup=user_keyboards.inline_keyboard)
    else:
        await callback.message.edit_caption(caption=txt[0], reply_markup=user_keyboards.inline_keyboard3)
    await callback.answer()


@router.callback_query(F.data == 'button_0_pressed')
async def process_button_1_press(callback: CallbackQuery):
    id = get_id(callback.message.caption)
    txt = get_info(search_by_id(id))
    if len(txt[5]) == 0:
        await callback.message.edit_caption(caption=txt[4], reply_markup=user_keyboards.inline_keyboard2)
    else:
        await callback.message.edit_caption(caption=txt[4], reply_markup=user_keyboards.inline_keyboard4)
    await callback.answer()


@router.callback_query(F.data == 'big_button_1_pressed')
async def process_button_1_press(callback: CallbackQuery):
    id = get_id(callback.message.caption)
    description = get_info(search_by_id(id))[1]
    name = callback.message.caption
    name = name[:name.find('(') - 1]
    if len(description) > 0:
        description = f'<i><b>{name}</b></i>\n\n' + description
        await callback.message.reply(description, reply_markup=user_keyboards.keyboard)
    else:
        description = f'Нет описания к <i><b>{name}</b></i>\n\n'
        await callback.message.reply(description, reply_markup=user_keyboards.keyboard)
    await callback.answer()


@router.callback_query(F.data == 'big_button_2_pressed')
async def process_button_1_press(callback: CallbackQuery):
    id = get_id(callback.message.caption)
    similar = get_info(search_by_id(id))[2]
    name = callback.message.caption
    name = name[:name.find('(') - 1]
    if len(similar) > 0:
        similar = f'Похожее на<i><b> {name}</b></i>\n\n' + similar
        await callback.message.reply(similar, reply_markup=user_keyboards.keyboard)
    else:
        similar = f'Для <i><b>{name}</b></i> не нашлось ничего похожего'
        await callback.message.reply(similar, reply_markup=user_keyboards.keyboard)
    await callback.answer()


@router.callback_query(F.data == 'big_button_3_pressed')
async def process_button_1_press(callback: CallbackQuery):
    id = get_id(callback.message.caption)
    trailer = get_info(search_by_id(id))[3]
    name = callback.message.caption
    name = name[:name.find('(') - 1]
    if len(trailer) > 0:
        trailer = f'Трейлер к <i><b>{name}</b></i>\n\n' + trailer
        await callback.message.reply(trailer, reply_markup=user_keyboards.keyboard)
    else:
        trailer = f'К сожалению, не нашлось трейлера для <i><b>{name}</b></i>'
        await callback.message.reply(trailer, reply_markup=user_keyboards.keyboard)
    await callback.answer()


@router.callback_query(F.data == 'big_button_4_pressed')
async def process_button_1_press(callback: CallbackQuery):
    id = get_id(callback.message.caption)
    facts = get_facts(id)
    name = callback.message.caption
    name = name[:name.find('(') - 1]
    if len(facts) > 0:
        facts = cut_back(facts)
        await callback.message.reply(
            f'Факты о <i><b>{name}</b></i>\n\n' + facts[0],
            reply_markup=user_keyboards.keyboard
        )
        for fact in facts[1:]:
            await callback.message.answer(fact, reply_markup=user_keyboards.keyboard)
    else:
        facts = f'Нет интересных фактов о <i><b>{name}</b></i>\n\n'
        await callback.message.reply(facts, reply_markup=user_keyboards.keyboard)
    await callback.answer()


@router.callback_query(F.data == 'big_button_5_pressed')
async def process_button_1_press(callback: CallbackQuery):
    id = get_id(callback.message.caption)
    sequels = get_info(search_by_id(id))[5]
    name = callback.message.caption
    name = name[:name.find('(') - 1]
    if len(sequels) > 0:
        sequels = f'Связанное с <i><b>{name}</b></i>\n\n' + sequels
        await callback.message.reply(sequels, reply_markup=user_keyboards.keyboard)
    else:
        trailer = f'К сожалению, не нашлось ничего связанного с <i><b>{name}</b></i>'
        await callback.message.reply(trailer, reply_markup=user_keyboards.keyboard)
    await callback.answer()


def _get_facts_by_page(movie_id: int, page: int = 0) -> Tuple[str, int]:
    facts = split_text(get_facts(movie_id), config.tg_bot.message_max_symbols)
    return facts[page], len(facts)
