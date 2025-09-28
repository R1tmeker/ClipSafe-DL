from __future__ import annotations

import logging

from aiogram import Bot

from .config import load_settings
from .texts import YTDL_REFUSAL_MESSAGE

logger = logging.getLogger(__name__)


class RightsConfirmationError(Exception):
    """Raised when a user refuses to confirm rights for the provided content."""


class ContentRightsManager:
    def __init__(self, bot: Bot) -> None:
        self.bot = bot
        self.settings = load_settings()

    async def confirm_user_rights(self, user_id: int) -> bool:
        # Placeholder: implement explicit confirmation flow via FSM.
        logger.debug("Confirming rights for user=%s", user_id)
        return True

    async def handle_restricted_platform(self, chat_id: int) -> None:
        await self.bot.send_message(chat_id, YTDL_REFUSAL_MESSAGE)

