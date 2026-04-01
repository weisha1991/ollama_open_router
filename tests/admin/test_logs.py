import pytest
from datetime import datetime
from ollama_router.admin.logs import parse_log_line, filter_logs, LogEntry


class TestParseLogLine:
    def test_parse_valid_log_line(self):
        line = "2026-03-30 20:24:45.346 INFO [req_72389c74] request_start method=POST path=/chat"
        entry = parse_log_line(line)
        assert entry is not None
        assert entry.level == "INFO"
        assert entry.request_id == "req_72389c74"
        assert entry.message == "request_start method=POST path=/chat"
        assert entry.timestamp.year == 2026

    def test_parse_debug_level(self):
        line = "2026-03-30 20:24:45.346 DEBUG [no-request] debug message here"
        entry = parse_log_line(line)
        assert entry is not None
        assert entry.level == "DEBUG"
        assert entry.request_id == "no-request"

    def test_parse_error_level(self):
        line = "2026-03-30 20:24:45.346 ERROR [req_abc123] something failed"
        entry = parse_log_line(line)
        assert entry is not None
        assert entry.level == "ERROR"

    def test_parse_warning_level(self):
        line = "2026-03-30 20:24:45.346 WARNING [req_xyz] warning message"
        entry = parse_log_line(line)
        assert entry is not None
        assert entry.level == "WARNING"

    def test_parse_critical_level(self):
        line = "2026-03-30 20:24:45.346 CRITICAL [req_123] critical error"
        entry = parse_log_line(line)
        assert entry is not None
        assert entry.level == "CRITICAL"

    def test_parse_padded_levels_from_actual_logs(self):
        """Test parsing with actual log format that includes level padding."""
        # INFO padded to 8 chars: "INFO    "
        line = "2026-03-30 20:24:45.346 INFO     [req_72389c74] request_start method=POST path=/chat"
        entry = parse_log_line(line)
        assert entry is not None
        assert entry.level == "INFO"
        assert entry.request_id == "req_72389c74"
        assert entry.message == "request_start method=POST path=/chat"

        # WARNING padded to 8 chars: "WARNING "
        line = "2026-03-30 20:24:45.346 WARNING  [req_xyz] warning message"
        entry = parse_log_line(line)
        assert entry is not None
        assert entry.level == "WARNING"

    def test_parse_invalid_line_returns_none(self):
        assert parse_log_line("invalid line") is None
        assert parse_log_line("") is None
        assert parse_log_line("2026-03-30 INFO missing brackets") is None

    def test_log_entry_to_dict(self):
        entry = LogEntry(
            timestamp=datetime(2026, 3, 30, 20, 24, 45, 346000),
            level="INFO",
            request_id="req_123",
            message="test message"
        )
        result = entry.to_dict()
        assert result["level"] == "INFO"
        assert result["request_id"] == "req_123"
        assert result["message"] == "test message"
        assert "2026-03-30T20:24:45.346" in result["timestamp"]


class TestFilterLogs:
    def test_filter_by_level(self):
        entries = [
            LogEntry(datetime(2026, 3, 30, 12, 0, 0), "INFO", "req_1", "msg1"),
            LogEntry(datetime(2026, 3, 30, 12, 1, 0), "DEBUG", "req_2", "msg2"),
            LogEntry(datetime(2026, 3, 30, 12, 2, 0), "ERROR", "req_3", "msg3"),
        ]
        filtered, total, has_more = filter_logs(
            iter(entries),
            start=None,
            end=None,
            levels={"INFO", "ERROR"}
        )
        assert total == 2
        assert len(filtered) == 2
        assert filtered[0].level == "INFO"
        assert filtered[1].level == "ERROR"

    def test_filter_by_time_range(self):
        entries = [
            LogEntry(datetime(2026, 3, 30, 10, 0, 0), "INFO", "req_1", "msg1"),
            LogEntry(datetime(2026, 3, 30, 12, 0, 0), "INFO", "req_2", "msg2"),
            LogEntry(datetime(2026, 3, 30, 14, 0, 0), "INFO", "req_3", "msg3"),
        ]
        start = datetime(2026, 3, 30, 11, 0, 0)
        end = datetime(2026, 3, 30, 13, 0, 0)
        filtered, total, has_more = filter_logs(
            iter(entries),
            start=start,
            end=end,
            levels=None
        )
        assert total == 1
        assert filtered[0].message == "msg2"

    def test_pagination(self):
        entries = [
            LogEntry(datetime(2026, 3, 30, i, 0, 0), "INFO", f"req_{i}", f"msg{i}")
            for i in range(10)
        ]
        filtered, total, has_more = filter_logs(
            iter(entries),
            start=None,
            end=None,
            levels=None,
            offset=0,
            limit=5
        )
        assert total == 10
        assert len(filtered) == 5
        assert has_more is True

        # Second page
        filtered, total, has_more = filter_logs(
            iter(entries),
            start=None,
            end=None,
            levels=None,
            offset=5,
            limit=5
        )
        assert total == 10
        assert len(filtered) == 5
        assert has_more is False

    def test_empty_entries(self):
        filtered, total, has_more = filter_logs(
            iter([]),
            start=None,
            end=None,
            levels=None
        )
        assert total == 0
        assert len(filtered) == 0
