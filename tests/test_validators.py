import math

import pytest

from app.validators import classify_url, parse_timecode


@pytest.mark.parametrize(
    "value, expected",
    [
        ("120", 120.0),
        ("02:30", 150.0),
        ("01:02:05.5", 3725.5),
        ("", None),
        ("not-a-time", None),
    ],
)
def test_parse_timecode(value, expected):
    result = parse_timecode(value)
    if expected is None:
        assert result is None
    else:
        assert result is not None
        assert math.isclose(result, expected, rel_tol=1e-6)


def test_classify_url_general_domain():
    info = classify_url("https://example.com/video.mp4")
    assert info.domain == "example.com"
    assert info.is_platform_restricted is False


def test_classify_url_restricted_domains():
    restricted_hosts = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://www.tiktok.com/@user/video/123",
    ]

    for url in restricted_hosts:
        info = classify_url(url)
        assert info.is_platform_restricted is True, url
