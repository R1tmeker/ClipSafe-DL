from __future__ import annotations

import asyncio
from contextlib import suppress

from aiogram import Bot
from aiogram.enums import ParseMode

from .bot import create_dispatcher
from .commands import setup_bot_commands
from .config import load_settings
from .jobs import JobQueue
from \.logs import setup_logging\nfrom \.migrations import run_migrations


async def _run_bot() -> None:
    setup_logging()
    settings = load_settings()
    if not settings.bot_token:
        raise RuntimeError("CLIPSAFE_BOT_TOKEN is not configured")

    queue = JobQueue(settings.redis_url)
    bot = Bot(token=settings.bot_token, parse_mode=ParseMode.HTML)
    bot["settings"] = settings
    bot["job_queue"] = queue

    dispatcher = create_dispatcher(settings, queue)
    await setup_bot_commands(bot)
    await dispatcher.start_polling(bot)


def main() -> None:
    with suppress(KeyboardInterrupt):
        asyncio.run(_run_bot())


if __name__ == "__main__":
    main()


