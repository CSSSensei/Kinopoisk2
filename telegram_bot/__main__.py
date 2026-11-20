import asyncio
import logging

from telegram_bot.bootstrap import run_bot

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")
    asyncio.run(run_bot())
