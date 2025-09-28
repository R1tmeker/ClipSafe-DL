from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from alembic import command
from alembic.config import Config

from .config import load_settings

logger = logging.getLogger(__name__)


def _alembic_config(database_url: str) -> Config:
    alembic_ini = Path("alembic.ini").resolve()
    if not alembic_ini.exists():
        raise FileNotFoundError("alembic.ini not found")

    cfg = Config(str(alembic_ini))
    cfg.set_main_option("sqlalchemy.url", database_url)
    script_location = str((alembic_ini.parent / "alembic").resolve())
    cfg.set_main_option("script_location", script_location)
    return cfg


def run_migrations(target: str = "head", *, url: Optional[str] = None) -> None:
    settings = load_settings()
    database_url = url or settings.database_url or "sqlite:///clipsafe.db"
    cfg = _alembic_config(database_url)
    logger.info("Running Alembic migrations up to %s", target)
    command.upgrade(cfg, target)


def downgrade_migrations(target: str = "base", *, url: Optional[str] = None) -> None:
    settings = load_settings()
    database_url = url or settings.database_url or "sqlite:///clipsafe.db"
    cfg = _alembic_config(database_url)
    logger.info("Downgrading Alembic migrations to %s", target)
    command.downgrade(cfg, target)


if __name__ == "__main__":
    run_migrations()
