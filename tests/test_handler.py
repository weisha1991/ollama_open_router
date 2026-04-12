# pyright: reportMissingImports=false

import httpx

from ollama_router.handler import KeyAction, RateLimitHandler


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
    assert cooldown.action == KeyAction.COOLDOWN


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
    assert cooldown.action == KeyAction.COOLDOWN


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
    assert cooldown.action == KeyAction.COOLDOWN


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
    assert cooldown.action == KeyAction.COOLDOWN


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
    assert cooldown.action == KeyAction.COOLDOWN


def test_detect_401_unauthorized_disables_key():
    handler = RateLimitHandler()

    response = httpx.Response(
        401,
        json={
            "error": "unauthorized",
            "signin_url": "https://ollama.com/connect?name=host&key=pub",
        },
    )

    cooldown = handler.detect_cooldown(response)
    assert cooldown is not None
    assert cooldown.action == KeyAction.DISABLE
    assert cooldown.reason == "unauthorized"
    assert cooldown.hours == 0


def test_detect_401_unauthorized_minimal_body():
    handler = RateLimitHandler()

    response = httpx.Response(401, json={"error": "unauthorized"})

    cooldown = handler.detect_cooldown(response)
    assert cooldown is not None
    assert cooldown.action == KeyAction.DISABLE


def test_detect_403_forbidden_model_unavailable():
    handler = RateLimitHandler(
        cooldown_session_hours=5, cooldown_weekly_hours=168, cooldown_rate_hours=4
    )

    response = httpx.Response(
        403,
        json={"error": "remote model is unavailable"},
    )

    cooldown = handler.detect_cooldown(response)
    assert cooldown is not None
    assert cooldown.action == KeyAction.COOLDOWN
    assert cooldown.reason == "model_unavailable"
    assert cooldown.hours == 5


def test_detect_403_forbidden_generic():
    handler = RateLimitHandler(
        cooldown_session_hours=5, cooldown_weekly_hours=168, cooldown_rate_hours=4
    )

    response = httpx.Response(
        403,
        json={"error": "cloud features are disabled"},
    )

    cooldown = handler.detect_cooldown(response)
    assert cooldown is not None
    assert cooldown.action == KeyAction.COOLDOWN
    assert cooldown.reason == "forbidden"


def test_detect_502_bad_gateway():
    handler = RateLimitHandler()

    response = httpx.Response(502, json={"error": "bad gateway"})

    cooldown = handler.detect_cooldown(response)
    assert cooldown is not None
    assert cooldown.action == KeyAction.COOLDOWN
    assert cooldown.reason == "bad_gateway"
    assert cooldown.hours == 0


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
