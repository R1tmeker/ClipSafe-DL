from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)
ENV_PREFIX = "CLIPSAFE_"


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    return os.environ.get(f"{ENV_PREFIX}{name}", default)


def _as_float(name: str, default: float) -> float:
    raw = _env(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        logger.warning("Invalid float for %s: %s. Using default %s.", name, raw, default)
        return default


def _as_int(name: str, default: int) -> int:
    raw = _env(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("Invalid int for %s: %s. Using default %s.", name, raw, default)
        return default


def _as_bool(name: str, default: bool) -> bool:
    raw = _env(name)
    if not raw:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _split_list(name: str) -> List[str]:
    raw = _env(name)
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _path(name: str, default: str) -> Path:
    raw = _env(name, default)
    return Path(raw).expanduser().resolve()


@dataclass(slots=True)
class Settings:
    bot_token: str
    redis_url: str = "redis://localhost:6379/0"
    max_file_gb: float = 2.0
    max_duration_hours: float = 6.0
    result_ttl_hours: int = 24
    jobs_per_hour: int = 5
    allowed_domains: List[str] = field(default_factory=list)
    storage_root: Path = Path("./data")
    temp_root: Path = Path("./data/temp")
    public_base_url: Optional[str] = None
    webhook_url: Optional[str] = None
    s3_endpoint: Optional[str] = None
    s3_bucket: Optional[str] = None
    s3_access_key: Optional[str] = None
    s3_secret_key: Optional[str] = None
    enable_analytics: bool = False

    def ensure_runtime_dirs(self) -> None:
        self.storage_root.mkdir(parents=True, exist_ok=True)
        self.temp_root.mkdir(parents=True, exist_ok=True)

    @property
    def max_file_bytes(self) -> int:
        return int(self.max_file_gb * 1024 * 1024 * 1024)

    @property
    def max_duration_seconds(self) -> int:
        return int(self.max_duration_hours * 3600)


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    bot_token = _env("BOT_TOKEN", "") or ""
    if not bot_token:
        logger.warning("CLIPSAFE_BOT_TOKEN is not set. Bot will not authenticate.")

    settings = Settings(
        bot_token=bot_token,
        redis_url=_env("REDIS_URL", "redis://localhost:6379/0"),
        max_file_gb=_as_float("MAX_FILE_GB", 2.0),
        max_duration_hours=_as_float("MAX_DURATION_H", 6.0),
        result_ttl_hours=_as_int("RESULT_TTL_H", 24),
        jobs_per_hour=_as_int("JOBS_PER_HOUR", 5),
        allowed_domains=_split_list("ALLOWED_DOMAINS"),
        storage_root=_path("STORAGE_ROOT", "./data"),
        temp_root=_path("TEMP_ROOT", "./data/tmp"),
        public_base_url=_env("PUBLIC_BASE_URL"),
        webhook_url=_env("WEBHOOK_URL"),
        s3_endpoint=_env("S3_ENDPOINT"),
        s3_bucket=_env("S3_BUCKET"),
        s3_access_key=_env("S3_ACCESS_KEY"),
        s3_secret_key=_env("S3_SECRET_KEY"),
        enable_analytics=_as_bool("ENABLE_ANALYTICS", False),
    )
    settings.ensure_runtime_dirs()
    return settings
