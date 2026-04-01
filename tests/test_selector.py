from ollama_router.state import KeySelector, KeyState, KeyStatus


def test_selector_polling():
    selector = KeySelector(
        [
            KeyState(key="key1", status=KeyStatus.AVAILABLE),
            KeyState(key="key2", status=KeyStatus.AVAILABLE),
            KeyState(key="key3", status=KeyStatus.AVAILABLE),
        ]
    )

    first = selector.select()
    assert first is not None
    assert first.key == "key1"

    second = selector.select()
    assert second is not None
    assert second.key == "key2"

    third = selector.select()
    assert third is not None
    assert third.key == "key3"

    fourth = selector.select()
    assert fourth is not None
    assert fourth.key == "key1"


def test_selector_skips_cooldown():
    from datetime import datetime, timezone, timedelta

    future = datetime.now(timezone.utc) + timedelta(hours=1)

    selector = KeySelector(
        [
            KeyState(
                key="key1",
                status=KeyStatus.COOLDOWN,
                cooldown_until=future,
                reason="rate_limit",
            ),
            KeyState(key="key2", status=KeyStatus.AVAILABLE),
        ]
    )

    result = selector.select()
    assert result is not None
    assert result.key == "key2"


def test_selector_all_cooldown_returns_none():
    from datetime import datetime, timezone, timedelta

    future = datetime.now(timezone.utc) + timedelta(hours=1)

    selector = KeySelector(
        [
            KeyState(
                key="key1",
                status=KeyStatus.COOLDOWN,
                cooldown_until=future,
                reason="rate_limit",
            ),
        ]
    )

    result = selector.select()
    assert result is None
