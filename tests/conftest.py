import pytest

from app.config import load_settings


@pytest.fixture(autouse=True)
def reset_settings_cache():
    load_settings.cache_clear()
    yield
    load_settings.cache_clear()
