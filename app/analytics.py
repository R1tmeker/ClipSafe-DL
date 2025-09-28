from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict

from .config import load_settings

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AnalyticsEvent:
    name: str
    payload: Dict[str, Any]


class AnalyticsClient:
    def __init__(self) -> None:
        self.settings = load_settings()

    def track(self, event: AnalyticsEvent) -> None:
        if not self.settings.enable_analytics:
            return
        logger.info("analytics event=%s payload=%s", event.name, event.payload)
