# pyright: reportMissingImports=false

import httpx

from ollama_router.handler import RateLimitHandler


def test_detect_session_usage_limit():
    handler = RateLimitHandler(
        cooldown_session_hours=5, cooldown_weekly_hours=168, cooldown_rate_hours=4
    )

    response = httpx.Response(
        429,
        json={"error": "you (user) have reached your session usage limit..."},
    )

    cooldown = handler.detect_cooldown(response)
    assert cooldown is not None
    assert cooldown.hours == 5
    assert cooldown.reason == "session_usage_limit"


def test_detect_rate_limit():
    handler = RateLimitHandler(
        cooldown_session_hours=5, cooldown_weekly_hours=168, cooldown_rate_hours=4
    )

    response = httpx.Response(
        429,
        json={"error": "too many requests, rate limit exceeded"},
    )

    cooldown = handler.detect_cooldown(response)
    assert cooldown is not None
    assert cooldown.hours == 4
    assert cooldown.reason == "rate_limit"


def test_detect_weekly_usage_limit_429():
    handler = RateLimitHandler(
        cooldown_session_hours=5, cooldown_weekly_hours=168, cooldown_rate_hours=4
    )

    response = httpx.Response(
        429,
        json={
            "error": "you (user) have reached your weekly usage limit, upgrade for higher limits: https://ollama.com/upgrade"
        },
    )

    cooldown = handler.detect_cooldown(response)
    assert cooldown is not None
    assert cooldown.hours == 168
    assert cooldown.reason == "weekly_usage_limit"


def test_detect_usage_limit_402():
    handler = RateLimitHandler(
        cooldown_session_hours=5, cooldown_weekly_hours=168, cooldown_rate_hours=4
    )

    response = httpx.Response(
        402,
        json={"error": "You've reached your usage limit, please upgrade to continue"},
    )

    cooldown = handler.detect_cooldown(response)
    assert cooldown is not None
    assert cooldown.hours == 5
    assert cooldown.reason == "usage_limit"


def test_detect_usage_limit_402_weekly():
    handler = RateLimitHandler(
        cooldown_session_hours=5, cooldown_weekly_hours=168, cooldown_rate_hours=4
    )

    response = httpx.Response(
        402,
        json={"error": "You've reached your weekly usage limit"},
    )

    cooldown = handler.detect_cooldown(response)
    assert cooldown is not None
    assert cooldown.hours == 168
    assert cooldown.reason == "weekly_usage_limit"


def test_no_cooldown_on_success():
    handler = RateLimitHandler()

    response = httpx.Response(200, json={"choices": []})

    cooldown = handler.detect_cooldown(response)
    assert cooldown is None


def test_no_cooldown_on_other_error():
    handler = RateLimitHandler()

    response = httpx.Response(500, json={"error": "internal server error"})

    cooldown = handler.detect_cooldown(response)
    assert cooldown is None


def test_unknown_429_uses_session_cooldown():
    handler = RateLimitHandler(
        cooldown_session_hours=5, cooldown_weekly_hours=168, cooldown_rate_hours=4
    )

    response = httpx.Response(
        429,
        json={"error": "some unknown error"},
    )

    cooldown = handler.detect_cooldown(response)
    assert cooldown is not None
    assert cooldown.hours == 5
    assert cooldown.reason == "unknown"
