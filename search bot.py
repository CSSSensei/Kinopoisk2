import time

import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import os
from dotenv import load_dotenv, find_dotenv
from draft import search_name, search_en_name

load_dotenv(find_dotenv())
API_URL: str = 'https://api.telegram.org/bot'
BOT_TOKEN: str = os.getenv('TOKEN')
ERROR_TEXT: str = 'Фильм не найден'
offset: int = -2
timeout: int = 60
updates: dict
engine = create_engine('mysql+pymysql://root:root@localhost:3306/new_schema')
                Session = sessionmaker(bind=engine)
                session = Session()
while True:
    start_time = time.time()
    updates = requests.get(f'{API_URL}{BOT_TOKEN}/getUpdates?offset={offset + 1}&timeout={timeout}').json()

    if updates['result']:
        for result in updates['result']:
            offset = result['update_id']
            chat_id = result['message']['from']['id']
            text = result['message'].get('text', '')
            films = []
            if text != '':
                print(text)
                films = search_name(session, text)
            flag = True
            if text != '' and len(films) == 0:
                requests.get(f'{API_URL}{BOT_TOKEN}/sendMessage?chat_id={chat_id}&text={ERROR_TEXT}')
            else:
                lst = ''

                for i in films:
                    if flag:
                        flag = False
                        id = i.id
                        link = f'https://st.kp.yandex.net/images/film_big/{id}.jpg'
                    if i.ru_name != None:
                        lst += i.ru_name + ' (' + str(i.year) + ')\n'
                    else:
                        lst += i.alternativeName + ' (' + str(i.year) + ')\n'
                if not flag:
                    requests.get(f'{API_URL}{BOT_TOKEN}/sendPhoto?chat_id={chat_id}&photo={link}')
                requests.get(
                    f'{API_URL}{BOT_TOKEN}/sendMessage?chat_id={chat_id}&text=Найдено {len(films)} фильмов:\n{lst}')

    end_time = time.time()
    print(f'Время между запросами к Telegram Bot API: {end_time - start_time}')
# from aiogram import Bot, Dispatcher
# from aiogram.filters import Command
# from aiogram.types import Message
#
# # Вместо BOT TOKEN HERE нужно вставить токен вашего бота,
# # полученный у @BotFather
# API_TOKEN: str = '6666760141:AAEf-A0GAFJTaXUm_1aemWE1Rk6tn4vkGJ8'
#
# # Создаем объекты бота и диспетчера
# bot: Bot = Bot(token=API_TOKEN)
# dp: Dispatcher = Dispatcher()
#
#
# # Этот хэндлер будет срабатывать на команду "/start"
# @dp.message(Command(commands=["start"]))
# async def process_start_command(message: Message):
#     await message.answer('Привет!\nМеня зовут Эхо-бот!\nНапиши мне что-нибудь')
#
#
# # Этот хэндлер будет срабатывать на команду "/help"
# @dp.message(Command(commands=["help"]))
# async def process_help_command(message: Message):
#     await message.answer('Напиши мне что-нибудь и в ответ '
#                          'я пришлю тебе твое сообщение')
#
#
# # Этот хэндлер будет срабатывать на любые ваши сообщения,
# # кроме команд "/start" и "/help"
# @dp.message()
# async def send_echo(message: Message):
#     try:
#         await message.copy_to(chat_id=message.chat.id)
#     except TypeError:
#         await message.reply(text='Данный тип апдейтов не поддерживается '
#                                  'методом send_copy')
#
#
# if __name__ == '__main__':
#     dp.run_polling(bot)