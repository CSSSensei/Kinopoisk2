from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart, BaseFilter, StateFilter
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from draft import search_name, search_en_name, random_film, get_info, get_facts, search_by_id
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import default_state, State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from UCommands import get_id, cut_back
from aiogram.types import (KeyboardButton, Message, ReplyKeyboardMarkup,
                           ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery)
import os
from dotenv import load_dotenv, find_dotenv


class check_id(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        for i in message.text[4:]:
            if i not in '0123456789':
                return False
        return message.text[1:4] == 'id_'


load_dotenv(find_dotenv())

API_TOKEN: str = os.getenv('TOKEN')
engine = create_engine('mysql+pymysql://root:root@localhost:3306/new_schema')
Session = sessionmaker(bind=engine)
session = Session()

storage: MemoryStorage = MemoryStorage()
# Создаем объекты бота и диспетчера
bot: Bot = Bot(token=API_TOKEN, parse_mode="HTML")
dp: Dispatcher = Dispatcher(storage=storage)


class FSMFillForm(StatesGroup):
    insert_film_name = State()  # Состояние ожидания ввода названия фильма


# Создаем объекты кнопок
button_1: KeyboardButton = KeyboardButton(text='Найти фильм')
button_2: KeyboardButton = KeyboardButton(text='Рандомный фильм')

# Создаем объект клавиатуры, добавляя в него кнопки
keyboard: ReplyKeyboardMarkup = ReplyKeyboardMarkup(
    keyboard=[[button_1], [button_2]],
    resize_keyboard=True,
    one_time_keyboard=True)
inline_button0: InlineKeyboardButton = InlineKeyboardButton(
    text='Больше информации о фильме',
    callback_data='button_0_pressed')
inline_button00: InlineKeyboardButton = InlineKeyboardButton(
    text='Меньше информации о фильме',
    callback_data='button_00_pressed')
inline_button1: InlineKeyboardButton = InlineKeyboardButton(
    text='Описание',
    callback_data='big_button_1_pressed')

inline_button2: InlineKeyboardButton = InlineKeyboardButton(
    text='Похожие фильмы',
    callback_data='big_button_2_pressed')
inline_button3: InlineKeyboardButton = InlineKeyboardButton(
    text='Трейлер',
    callback_data='big_button_3_pressed')
inline_button4: InlineKeyboardButton = InlineKeyboardButton(
    text='Интересные факты о фильме',
    callback_data='big_button_4_pressed')
inline_button5: InlineKeyboardButton = InlineKeyboardButton(
    text='Сиквелы и приквелы',
    callback_data='big_button_5_pressed')

# Создаем объект инлайн-клавиатуры
inline_keyboard: InlineKeyboardMarkup = InlineKeyboardMarkup(
    inline_keyboard=[[inline_button0],
                     [inline_button1, inline_button2],
                     [inline_button3, inline_button4]])
inline_keyboard2: InlineKeyboardMarkup = InlineKeyboardMarkup(
    inline_keyboard=[[inline_button00],
                     [inline_button1, inline_button2],
                     [inline_button3, inline_button4]])
inline_keyboard3: InlineKeyboardMarkup = InlineKeyboardMarkup(
    inline_keyboard=[[inline_button0],
                     [inline_button1, inline_button2],
                     [inline_button3, inline_button4],
                     [inline_button5]])
inline_keyboard4: InlineKeyboardMarkup = InlineKeyboardMarkup(
    inline_keyboard=[[inline_button00],
                     [inline_button1, inline_button2],
                     [inline_button3, inline_button4],
                     [inline_button5]])




# Этот хэндлер будет срабатывать на команду "/start"
@dp.message(CommandStart())
async def process_start_command(message: Message):
    await message.answer('Привет!\nМеня зовут CineBot!\nНапиши /help чтобы узнать, как пользоваться ботом',
                         reply_markup=keyboard)


@dp.message(Command(commands='cancel'), StateFilter(default_state))
async def process_cancel_command(message: Message):
    await message.answer(text='Отменять нечего. Вы вне машины состояний\n\n')


@dp.message(Command(commands='cancel'), ~StateFilter(default_state))
async def process_cancel_command_state(message: Message, state: FSMContext):
    await message.answer(text='Вы вышли из поиска фильмов', reply_markup=keyboard)
    await state.clear()


# Этот хэндлер будет срабатывать на команду "/help"
@dp.message(Command(commands=['help']))
async def process_help_command(message: Message):
    await message.answer(
        '🌟 Лови горячие команды для поиска фильмов и сериалов! 🎬🔎\n✨ /id_xxxx: используй эту команду, чтобы мгновенно найти фильм или сериал по уникальному идентификатору.\n💫 "Найти фильм": просто введи название фильма или сериала, и я помогу найти его. Не беспокойся о регистре, но старайся соблюдать орфографию, чтобы результат был точным. Если что, посмотри правильное название на Кинопоиске.\n🌟 "Рандомный фильм": дай мне шанс удивить тебя! Я найду случайный фильм с рейтингом не менее 7.0 на КиноПоиске и с количеством оценок не меньше 50 тысяч. Подготовься к незабываемому просмотру! 🍿🎉')


@dp.message(check_id())
async def search(message: Message):
    s = message.text[4:]
    id = int(s)
    line = search_by_id(id)
    if line is not None:
        txt = get_info(line)
        link = f'https://st.kp.yandex.net/images/film_big/{id}.jpg'
        if len(txt[5]) == 0:
            await bot.send_photo(message.chat.id, photo=link, caption=txt[0], reply_markup=inline_keyboard)
        else:
            await bot.send_photo(message.chat.id, photo=link, caption=txt[0], reply_markup=inline_keyboard3)
    else:
        await message.answer('Такого id не существует')


@dp.message(F.text == 'Найти фильм')
async def process_insert_film_name(message: Message, state: FSMContext):
    await message.answer(text='Введите название фильма', reply_markup=ReplyKeyboardRemove())
    await state.set_state(FSMFillForm.insert_film_name)


@dp.message(F.text == 'Рандомный фильм', ~StateFilter(FSMFillForm.insert_film_name))
async def process_random_film(message: Message):
    line = random_film()
    id = line.id
    link = f'https://st.kp.yandex.net/images/film_big/{id}.jpg'
    txt = get_info(line)
    if len(txt[5]) == 0:
        await bot.send_photo(message.chat.id, photo=link, caption=txt[0], reply_markup=inline_keyboard)
    else:
        await bot.send_photo(message.chat.id, photo=link, caption=txt[0], reply_markup=inline_keyboard3)



@dp.callback_query(F.data == 'button_00_pressed')
async def process_button_1_press(callback: CallbackQuery):
    id = get_id(callback.message.caption)
    txt = get_info(search_by_id(id))
    if len(txt[5]) == 0:
        await callback.message.edit_caption(caption=txt[0], reply_markup=inline_keyboard)
    else:
        await callback.message.edit_caption(caption=txt[0], reply_markup=inline_keyboard3)

@dp.callback_query(F.data == 'button_0_pressed')
async def process_button_1_press(callback: CallbackQuery):
    id = get_id(callback.message.caption)
    txt = get_info(search_by_id(id))
    if len(txt[5]) == 0:
        await callback.message.edit_caption(caption=txt[4], reply_markup=inline_keyboard2)
    else:
        await callback.message.edit_caption(caption=txt[4], reply_markup=inline_keyboard4)


@dp.callback_query(F.data == 'big_button_1_pressed')
async def process_button_1_press(callback: CallbackQuery):
    id = get_id(callback.message.caption)
    description = get_info(search_by_id(id))[1]
    name = callback.message.caption
    name = name[:name.find('(') - 1]
    if len(description) > 0:
        description = f'<i><b>{name}</b></i>\n\n' + description
        await callback.message.reply(description, reply_markup=keyboard)
    else:
        description = f'Нет описания к <i><b>{name}</b></i>\n\n'
        await callback.message.reply(description, reply_markup=keyboard)


@dp.callback_query(F.data == 'big_button_2_pressed')
async def process_button_1_press(callback: CallbackQuery):
    id = get_id(callback.message.caption)
    similar = get_info(search_by_id(id))[2]
    name = callback.message.caption
    name = name[:name.find('(') - 1]
    if len(similar) > 0:
        similar = f'Похожее на<i><b> {name}</b></i>\n\n' + similar
        await callback.message.reply(similar, reply_markup=keyboard)
    else:
        similar = f'Для <i><b>{name}</b></i> не нашлось ничего похожего'
        await callback.message.reply(similar, reply_markup=keyboard)


@dp.callback_query(F.data == 'big_button_3_pressed')
async def process_button_1_press(callback: CallbackQuery):
    id = get_id(callback.message.caption)
    trailer = get_info(search_by_id(id))[3]
    name = callback.message.caption
    name = name[:name.find('(') - 1]
    if len(trailer) > 0:
        trailer = f'Трейлер к <i><b>{name}</b></i>\n\n' + trailer
        await callback.message.reply(trailer, reply_markup=keyboard)
    else:
        trailer = f'К сожалению, не нашлось трейлера для <i><b>{name}</b></i>'
        await callback.message.reply(trailer, reply_markup=keyboard)


@dp.callback_query(F.data == 'big_button_4_pressed')
async def process_button_1_press(callback: CallbackQuery):
    id = get_id(callback.message.caption)
    facts = get_facts(id)
    name = callback.message.caption
    name = name[:name.find('(') - 1]
    if len(facts) > 0:
        if len(facts) > 2048:
            facts = cut_back(facts)
            await callback.message.reply(f'Факты о <i><b>{name}</b></i>\n\n' + facts[0],
                                         reply_markup=keyboard)
            for i in range(1, len(facts)):
                await callback.message.answer(facts[i], reply_markup=keyboard)
        else:
            facts = f'Факты о <i><b>{name}</b></i>\n\n' + facts
            await callback.message.reply(facts, reply_markup=keyboard)
    else:
        facts = f'Нет интересных фактов о <i><b>{name}</b></i>\n\n'
        await callback.message.reply(facts, reply_markup=keyboard)

@dp.callback_query(F.data == 'big_button_5_pressed')
async def process_button_1_press(callback: CallbackQuery):
    id = get_id(callback.message.caption)
    sequels = get_info(search_by_id(id))[5]
    name = callback.message.caption
    name = name[:name.find('(') - 1]
    if len(sequels) > 0:
        sequels = f'Связанное с <i><b>{name}</b></i>\n\n' + sequels
        await callback.message.reply(sequels, reply_markup=keyboard)
    else:
        trailer = f'К сожалению, не нашлось ничего связанного с <i><b>{name}</b></i>'
        await callback.message.reply(trailer, reply_markup=keyboard)

@dp.message(StateFilter(FSMFillForm.insert_film_name))
async def return_film_info(message: Message, state: FSMContext):
    text = message.text
    films = []
    if text != '':
        print(text)
        films = search_en_name(session, text)

    flag = True
    if text != '' and len(films) == 0:
        await message.answer('Фильмов не найдено', reply_markup=keyboard)
    else:
        lst = ''
        for i in films:
            if flag:
                flag = False
                id = i.id
                link = f'https://st.kp.yandex.net/images/film_big/{id}.jpg'
            if i.ru_name != None:
                lst += i.ru_name
            else:
                lst += i.alternativeName
            lst += f' ({i.year}, рейтинг КП: {i.rating_kp})   <i>/id_{i.id}</i>\n'
        if not flag:
            await bot.send_photo(message.chat.id, photo=link)
        await message.answer(lst, reply_markup=keyboard)
        await state.clear()


@dp.message()
async def process_name_command(message: Message):
    await message.answer(text='К сожалению, я не понимаю о чем вы', reply_markup=keyboard)


if __name__ == '__main__':
    dp.run_polling(bot)
