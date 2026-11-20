import os
from dataclasses import dataclass
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())


@dataclass
class BotConfig:
    token: str
    message_max_symbols: int = 400


config = BotConfig(token=os.getenv('BOT_TOKEN'))
