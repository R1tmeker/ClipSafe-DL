from __future__ import annotations

import pytest

from app.antispam import AntiSpam, RateLimitExceeded


def test_antispam_limits(monkeypatch):
    monkeypatch.setenv("CLIPSAFE_JOBS_PER_HOUR", "2")
    anti = AntiSpam()

    anti.register_job(42)
    anti.register_job(42)

    with pytest.raises(RateLimitExceeded):
        anti.register_job(42)


def test_antispam_isolated_users(monkeypatch):
    monkeypatch.setenv("CLIPSAFE_JOBS_PER_HOUR", "1")
    anti = AntiSpam()

    anti.register_job(1)
    # Другой пользователь не влияет на лимит
    anti.register_job(2)

