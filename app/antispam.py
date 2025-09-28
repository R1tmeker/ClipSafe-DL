from __future__ import annotations

import logging
from datetime import datetime, timedelta

from .config import load_settings

logger = logging.getLogger(__name__)


class RateLimitExceeded(Exception):
    pass


class AntiSpam:
    def __init__(self) -> None:
        self.settings = load_settings()
        self._bucket: dict[int, list[datetime]] = {}

    def register_job(self, user_id: int) -> None:
        now = datetime.utcnow()
        window = now - timedelta(hours=1)
        history = self._bucket.setdefault(user_id, [])
        history[:] = [item for item in history if item > window]
        if len(history) >= self.settings.jobs_per_hour:
            logger.info("AntiSpam reject user=%s", user_id)
            raise RateLimitExceeded("Превышено количество задач в час")
        history.append(now)

