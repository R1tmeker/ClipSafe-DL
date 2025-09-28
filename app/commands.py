from __future__ import annotations

from aiogram import Bot
from aiogram.types import BotCommand


async def setup_bot_commands(bot: Bot) -> None:
    commands = [
        BotCommand(command="start", description="Приветствие и обзор возможностей"),
        BotCommand(command="help", description="Справка по операциям"),
        BotCommand(command="upload", description="Как загрузить файл"),
        BotCommand(command="link", description="Обработка прямой ссылки"),
        BotCommand(command="trim", description="Запрос временных меток"),
        BotCommand(command="format", description="Выбор контейнера вывода"),
        BotCommand(command="queue", description="Статус текущих задач"),
        BotCommand(command="cancel", description="Отмена активной задачи"),
    ]
    await bot.set_my_commands(commands)
