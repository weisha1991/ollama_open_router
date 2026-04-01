import pytest
from ollama_router.request_context import (
    request_id_var,
    get_request_id,
    set_request_id,
    generate_request_id,
    RequestIdFilter,
)


def test_get_request_id_default():
    """Test default request ID when not set."""
    request_id_var.set(None)
    assert get_request_id() == "no-request"


def test_set_and_get_request_id():
    """Test setting and getting request ID."""
    token = set_request_id("req_test123")
    assert get_request_id() == "req_test123"
    request_id_var.reset(token)


def test_request_id_filter():
    """Test that filter injects request_id into log record."""
    import logging

    filter = RequestIdFilter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="test message",
        args=(),
        exc_info=None,
    )

    request_id_var.set(None)
    filter.filter(record)
    assert record.request_id == "no-request"

    token = set_request_id("req_abc123")
    filter.filter(record)
    assert record.request_id == "req_abc123"
    request_id_var.reset(token)


def test_generate_request_id():
    """Test request ID generation."""
    id1 = generate_request_id()
    id2 = generate_request_id()
    assert id1 != id2
    assert id1.startswith("req_")
    assert len(id1) == 12  # "req_" (4) + 8 hex chars
