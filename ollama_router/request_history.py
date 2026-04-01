"""Request history tracking for admin dashboard."""

from collections import deque
from dataclasses import dataclass, asdict
from datetime import datetime, timezone


@dataclass
class RequestRecord:
    """Record of a single request."""

    timestamp: datetime
    request_id: str
    method: str
    path: str
    status_code: int
    key_id: str | None
    latency_ms: float

    def to_dict(self) -> dict:
        """Serialize to dict for JSON response."""
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        return d


class RequestHistory:
    """In-memory request history with max size limit."""

    def __init__(self, max_size: int = 1000):
        self._records: deque[RequestRecord] = deque(maxlen=max_size)

    def add(self, record: RequestRecord) -> None:
        """Add a record to history."""
        self._records.append(record)

    def get_all(self) -> list[RequestRecord]:
        """Get all records as list."""
        return list(self._records)

    def to_dict_list(self) -> list[dict]:
        """Serialize all records to dict list."""
        return [r.to_dict() for r in self._records]

    def __len__(self) -> int:
        """Return number of records."""
        return len(self._records)
