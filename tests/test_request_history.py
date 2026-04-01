import pytest
from datetime import datetime, timezone
from ollama_router.request_history import RequestRecord, RequestHistory


def test_request_record_creation():
    record = RequestRecord(
        timestamp=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
        request_id="req_abc123",
        method="POST",
        path="/chat/completions",
        status_code=200,
        key_id="key_xyz789",
        latency_ms=150.5,
    )
    assert record.status_code == 200
    assert record.latency_ms == 150.5


def test_request_history_add_and_get():
    history = RequestHistory(max_size=3)
    record = RequestRecord(
        timestamp=datetime.now(timezone.utc),
        request_id="req_123",
        method="GET",
        path="/health",
        status_code=200,
        key_id=None,
        latency_ms=10.0,
    )
    history.add(record)
    records = history.get_all()
    assert len(records) == 1
    assert records[0].request_id == "req_123"


def test_request_history_max_size():
    history = RequestHistory(max_size=2)
    for i in range(5):
        record = RequestRecord(
            timestamp=datetime.now(timezone.utc),
            request_id=f"req_{i}",
            method="GET",
            path="/test",
            status_code=200,
            key_id=None,
            latency_ms=float(i),
        )
        history.add(record)
    records = history.get_all()
    assert len(records) == 2
    assert records[0].request_id == "req_3"
    assert records[1].request_id == "req_4"


def test_request_history_to_dict_list():
    history = RequestHistory(max_size=10)
    record = RequestRecord(
        timestamp=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
        request_id="req_123",
        method="POST",
        path="/chat",
        status_code=200,
        key_id="key_abc",
        latency_ms=100.0,
    )
    history.add(record)
    dict_list = history.to_dict_list()
    assert len(dict_list) == 1
    assert dict_list[0]["request_id"] == "req_123"
    assert dict_list[0]["timestamp"] == "2024-01-15T10:30:00+00:00"
