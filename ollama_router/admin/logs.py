import re
from dataclasses import dataclass
from datetime import datetime
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
        timestamp = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S.%f")
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
