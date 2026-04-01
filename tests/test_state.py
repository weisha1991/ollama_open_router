from datetime import datetime, timedelta, timezone

from ollama_router.state import KeyState, KeyStatus, StateStore


def test_key_state_available():
    state = KeyState(
        key="test_key",
        status=KeyStatus.AVAILABLE,
        cooldown_until=None,
        reason=None,
    )
    assert state.status == KeyStatus.AVAILABLE
    assert state.is_available() is True


def test_key_state_cooldown():
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    state = KeyState(
        key="test_key",
        status=KeyStatus.COOLDOWN,
        cooldown_until=future,
        reason="session_usage_limit",
    )
    assert state.status == KeyStatus.COOLDOWN
    assert state.is_available() is False


def test_state_store_persistence(tmp_path):
    store = StateStore(state_dir=str(tmp_path))
    store.keys = [
        KeyState(key="key1", status=KeyStatus.AVAILABLE),
        KeyState(
            key="key2",
            status=KeyStatus.COOLDOWN,
            cooldown_until=datetime.now(timezone.utc) + timedelta(hours=1),
            reason="rate_limit",
        ),
    ]
    store.save()

    store2 = StateStore(state_dir=str(tmp_path))
    store2.load()
    assert len(store2.keys) == 2
    assert store2.keys[1].status == KeyStatus.COOLDOWN
