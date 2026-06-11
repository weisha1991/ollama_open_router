from datetime import datetime, timezone

from ollama_router.admin.views import _build_dashboard_context
from ollama_router.request_history import RequestHistory, RequestRecord
from ollama_router.state import KeySelector, KeyState, KeyStatus


def _make_history() -> RequestHistory:
    history = RequestHistory(max_size=20)
    history.add(
        RequestRecord(
            timestamp=datetime(2026, 6, 10, 10, 0, tzinfo=timezone.utc),
            request_id="req_a",
            method="POST",
            path="/v1/chat/completions",
            status_code=200,
            key_id="key-a",
            latency_ms=240,
        )
    )
    history.add(
        RequestRecord(
            timestamp=datetime(2026, 6, 10, 11, 0, tzinfo=timezone.utc),
            request_id="req_b",
            method="POST",
            path="/v1/messages",
            status_code=429,
            key_id="key-b",
            latency_ms=820,
        )
    )
    return history


def test_build_dashboard_context_returns_cards_trend_distribution_and_lists():
    selector = KeySelector(
        [
            KeyState(key="alpha", status=KeyStatus.AVAILABLE),
            KeyState(key="beta", status=KeyStatus.COOLDOWN),
            KeyState(key="gamma", status=KeyStatus.DISABLED),
        ]
    )
    selector.last_used_key = "alpha"
    history = _make_history()

    dashboard = _build_dashboard_context(selector, history)

    assert dashboard["stats"]["total_keys"] == 3
    assert dashboard["distribution"]["available"] == 1
    assert dashboard["distribution"]["cooldown"] == 1
    assert dashboard["distribution"]["disabled"] == 1
    assert len(dashboard["request_overview"]) >= 1
    assert len(dashboard["recent_keys"]) == 3
    assert len(dashboard["recent_activity"]) == 2


def test_recent_activity_keeps_latest_requests_first():
    selector = KeySelector([KeyState(key="alpha")])
    history = _make_history()

    dashboard = _build_dashboard_context(selector, history)

    assert dashboard["recent_activity"][0]["request_id"] == "req_b"
    assert dashboard["recent_activity"][1]["request_id"] == "req_a"


def test_request_overview_buckets_history_without_empty_failure():
    selector = KeySelector([KeyState(key="alpha")])
    history = RequestHistory(max_size=20)

    dashboard = _build_dashboard_context(selector, history)

    assert dashboard["request_overview"] == []
    assert dashboard["recent_activity"] == []
    assert dashboard["request_summary"]["state"] == "empty"


def test_request_summary_marks_single_bucket_as_collecting():
    selector = KeySelector([KeyState(key="alpha")])
    history = RequestHistory(max_size=20)
    history.add(
        RequestRecord(
            timestamp=datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc),
            request_id="req_single",
            method="POST",
            path="/v1/chat/completions",
            status_code=200,
            key_id="key-a",
            latency_ms=120,
        )
    )

    dashboard = _build_dashboard_context(selector, history)

    assert len(dashboard["request_overview"]) == 1
    assert dashboard["request_summary"]["state"] == "single"
    assert dashboard["request_summary"]["latest"] == 1
