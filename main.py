from dotenv import load_dotenv

# Загружаем .env до импорта модулей бота и чтения переменных окружения.
load_dotenv()

import os
import sys
import logging

from bot.client import create_bot


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    token = os.getenv("DISCORD_TOKEN", "").strip()
    if not token:
        print("Не задан DISCORD_TOKEN. Скопируйте .env.example в .env и вставьте токен.")
        sys.exit(1)

    bot = create_bot()
    bot.run(token, log_handler=None)


if __name__ == "__main__":
    main()
