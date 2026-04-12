from ollama_router.state import KeySelector, KeyState, KeyStatus


def test_selector_returns_available_key():
    selector = KeySelector(
        [
            KeyState(key="key1", status=KeyStatus.AVAILABLE),
            KeyState(key="key2", status=KeyStatus.AVAILABLE),
            KeyState(key="key3", status=KeyStatus.AVAILABLE),
        ]
    )

    selected = selector.select()
    assert selected is not None
    assert selected.key in ("key1", "key2", "key3")


def test_selector_smart_shuffle_distributes():
    selector = KeySelector(
        [
            KeyState(key="key1", status=KeyStatus.AVAILABLE),
            KeyState(key="key2", status=KeyStatus.AVAILABLE),
            KeyState(key="key3", status=KeyStatus.AVAILABLE),
        ]
    )

    picked = set()
    for _ in range(30):
        result = selector.select()
        if result:
            picked.add(result.key)

    assert len(picked) >= 2


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
