import asyncio
import logging
import re
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


LOG_PATTERN = re.compile(
    r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}) "
    r"(DEBUG|INFO|WARNING|ERROR|CRITICAL)\s+"
    r"\[([^\]]+)\] "
    r"(.+)"
)


@dataclass
class LogEntry:
    timestamp: datetime
    level: str
    request_id: str
    message: str

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "timestamp": self.timestamp.isoformat(timespec="milliseconds"),
            "level": self.level,
            "request_id": self.request_id,
            "message": self.message,
        }


def parse_log_line(line: str) -> LogEntry | None:
    """Parse a single log line into LogEntry or return None if invalid."""
    if not line:
        return None
    match = LOG_PATTERN.match(line)
    if not match:
        return None
    ts_str, level, req_id, msg = match.groups()
    try:
        timestamp = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S.%f").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return LogEntry(
        timestamp=timestamp,
        level=level,
        request_id=req_id,
        message=msg,
    )


def read_log_file(path: Path) -> Iterator[LogEntry]:
    """Read and parse log file line by line."""
    if not path.exists():
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            entry = parse_log_line(line.strip())
            if entry:
                yield entry


def filter_logs(
    entries: Iterator[LogEntry],
    start: datetime | None,
    end: datetime | None,
    levels: set[str] | None,
    offset: int = 0,
    limit: int = 1000,
) -> tuple[list[LogEntry], int, bool]:
    """Filter log entries by time and level with pagination.

    Returns:
        tuple of (filtered_entries, total_count, has_more)
    """
    all_matching = []
    for entry in entries:
        if start and entry.timestamp < start:
            continue
        if end and entry.timestamp > end:
            continue
        if levels and entry.level not in levels:
            continue
        all_matching.append(entry)

    total = len(all_matching)
    paginated = all_matching[offset:offset + limit]
    has_more = offset + limit < total
    return paginated, total, has_more


class LogBroadcaster(logging.Handler):
    """Custom logging handler that broadcasts LogEntry to SSE subscribers.

    Instead of tailing the log file (which breaks on rotation and buffering),
    this handler receives LogRecord directly from the logging pipeline and
    pushes structured LogEntry objects to in-memory asyncio.Queue subscribers.
    """

    def __init__(self, capacity: int = 1000):
        super().__init__()
        self.entries: deque[LogEntry] = deque(maxlen=capacity)
        self._subscribers: list[asyncio.Queue[LogEntry]] = []

    def emit(self, record: logging.LogRecord) -> None:
        """Convert LogRecord to LogEntry and broadcast to all subscribers."""
        try:
            entry = LogEntry(
                timestamp=datetime.fromtimestamp(record.created, tz=timezone.utc),
                level=record.levelname,
                request_id=getattr(record, "request_id", "no-request"),
                message=record.getMessage(),
            )
            self.entries.append(entry)

            dead: list[asyncio.Queue[LogEntry]] = []
            for q in self._subscribers:
                try:
                    q.put_nowait(entry)
                except asyncio.QueueFull:
                    dead.append(q)
            for q in dead:
                self._subscribers.remove(q)
        except Exception:
            self.handleError(record)

    def subscribe(self, maxsize: int = 500) -> asyncio.Queue[LogEntry]:
        """Create a new subscriber queue that will receive future log entries."""
        queue: asyncio.Queue[LogEntry] = asyncio.Queue(maxsize=maxsize)
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[LogEntry]) -> None:
        """Remove a subscriber queue."""
        try:
            self._subscribers.remove(queue)
        except ValueError:
            pass

    def get_recent(
        self, levels: set[str] | None = None, limit: int = 100
    ) -> list[LogEntry]:
        """Return recent log entries, optionally filtered by level."""
        entries = list(self.entries)
        if levels:
            entries = [e for e in entries if e.level in levels]
        return entries[-limit:]
