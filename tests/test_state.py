from datetime import datetime, timedelta, timezone

from ollama_router.state import KeySelector, KeyState, KeyStatus, StateStore


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


def test_key_state_disabled():
    state = KeyState(
        key="test_key",
        status=KeyStatus.DISABLED,
        reason="unauthorized",
    )
    assert state.status == KeyStatus.DISABLED
    assert state.is_available() is False


def test_key_state_disabled_never_becomes_available():
    state = KeyState(
        key="test_key",
        status=KeyStatus.DISABLED,
        cooldown_until=datetime.now(timezone.utc) - timedelta(hours=999),
        reason="unauthorized",
    )
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


def test_state_store_disabled_persistence(tmp_path):
    store = StateStore(state_dir=str(tmp_path))
    store.keys = [
        KeyState(key="key1", status=KeyStatus.DISABLED, reason="unauthorized"),
        KeyState(key="key2", status=KeyStatus.AVAILABLE),
    ]
    store.save()

    store2 = StateStore(state_dir=str(tmp_path))
    store2.load()
    assert len(store2.keys) == 2
    assert store2.keys[0].status == KeyStatus.DISABLED
    assert store2.keys[0].reason == "unauthorized"


def test_key_selector_skips_disabled_keys():
    keys = [
        KeyState(key="key1", status=KeyStatus.DISABLED, reason="unauthorized"),
        KeyState(key="key2", status=KeyStatus.AVAILABLE),
    ]
    selector = KeySelector(keys=keys)

    selected = selector.select()
    assert selected is not None
    assert selected.key == "key2"


def test_key_selector_mark_disabled():
    keys = [
        KeyState(key="key1", status=KeyStatus.AVAILABLE),
        KeyState(key="key2", status=KeyStatus.AVAILABLE),
    ]
    selector = KeySelector(keys=keys)

    selector.mark_disabled("key1", "unauthorized")
    assert selector.keys[0].status == KeyStatus.DISABLED
    assert selector.keys[0].reason == "unauthorized"
    assert selector.keys[0].cooldown_until is None

    selected = selector.select()
    assert selected is not None
    assert selected.key == "key2"


def test_key_selector_smart_shuffle_avoids_last_failed_key():
    keys = [
        KeyState(key="key1", status=KeyStatus.AVAILABLE),
        KeyState(key="key2", status=KeyStatus.AVAILABLE),
        KeyState(key="key3", status=KeyStatus.AVAILABLE),
    ]
    selector = KeySelector(keys=keys, last_failed_key="key2")

    picked_keys = set()
    for _ in range(50):
        selected = selector.select()
        if selected:
            picked_keys.add(selected.key)

    assert "key1" in picked_keys
    assert "key3" in picked_keys
    assert len(picked_keys) >= 2


def test_key_selector_update_last_failed_key():
    keys = [
        KeyState(key="key1", status=KeyStatus.AVAILABLE),
        KeyState(key="key2", status=KeyStatus.AVAILABLE),
    ]
    selector = KeySelector(keys=keys)

    assert selector.last_failed_key is None

    selector.update_last_failed_key("key1")
    assert selector.last_failed_key == "key1"

    selector.update_last_failed_key(None)
    assert selector.last_failed_key is None


def test_state_store_last_failed_key_persistence(tmp_path):
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
    store.last_failed_key = "key2"
    store.save()

    store2 = StateStore(state_dir=str(tmp_path))
    store2.load()
    assert store2.last_failed_key == "key2"


def test_state_store_last_failed_key_null_persistence(tmp_path):
    store = StateStore(state_dir=str(tmp_path))
    store.keys = [KeyState(key="key1", status=KeyStatus.AVAILABLE)]
    store.last_failed_key = None
    store.save()

    store2 = StateStore(state_dir=str(tmp_path))
    store2.load()
    assert store2.last_failed_key is None
