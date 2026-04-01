# pyright: reportMissingImports=false

import httpx

from ollama_router.handler import RateLimitHandler


def test_detect_session_limit():
    handler = RateLimitHandler(cooldown_session_hours=72, cooldown_rate_hours=4)

    response = httpx.Response(
        429,
        json={"error": "you (user) have reached your session usage limit..."},
    )

    cooldown = handler.detect_cooldown(response)
    assert cooldown is not None
    assert cooldown.hours == 72
    assert cooldown.reason == "session_usage_limit"


def test_detect_rate_limit():
    handler = RateLimitHandler(cooldown_session_hours=72, cooldown_rate_hours=4)

    response = httpx.Response(
        429,
        json={"error": "too many requests, rate limit exceeded"},
    )

    cooldown = handler.detect_cooldown(response)
    assert cooldown is not None
    assert cooldown.hours == 4
    assert cooldown.reason == "rate_limit"


def test_no_cooldown_on_success():
    handler = RateLimitHandler()

    response = httpx.Response(200, json={"choices": []})

    cooldown = handler.detect_cooldown(response)
    assert cooldown is None
