from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
from pathlib import Path
import random
from threading import Lock


class KeyStatus(Enum):
    AVAILABLE = "available"
    COOLDOWN = "cooldown"
    DISABLED = "disabled"


@dataclass
class KeyState:
    key: str
    status: KeyStatus = KeyStatus.AVAILABLE
    cooldown_until: datetime | None = None
    reason: str | None = None
    active_streams: int = 0

    def is_available(self) -> bool:
        if self.status == KeyStatus.DISABLED:
            return False
        if self.status == KeyStatus.AVAILABLE:
            return True
        if self.cooldown_until and datetime.now(timezone.utc) > self.cooldown_until:
            self.status = KeyStatus.AVAILABLE
            self.cooldown_until = None
            return True
        return False


@dataclass
class StateStore:
    state_dir: str
    keys: list[KeyState] = field(default_factory=list)
    current_index: int = 0
    last_failed_key: str | None = None

    def save(self):
        path = Path(self.state_dir)
        path.mkdir(parents=True, exist_ok=True)

        data = {
            "keys": [
                {
                    "key": k.key,
                    "status": k.status.value,
                    "cooldown_until": k.cooldown_until.isoformat()
                    if k.cooldown_until
                    else None,
                    "reason": k.reason,
                }
                for k in self.keys
            ],
            "current_index": self.current_index,
            "last_failed_key": self.last_failed_key,
        }

        with open(path / "key_states.json", "w") as f:
            json.dump(data, f, indent=2)

    def load(self):
        path = Path(self.state_dir) / "key_states.json"
        if not path.exists():
            return

        with open(path) as f:
            data = json.load(f)

        self.keys = [
            KeyState(
                key=k["key"],
                status=KeyStatus(k["status"]),
                cooldown_until=datetime.fromisoformat(k["cooldown_until"])
                if k["cooldown_until"]
                else None,
                reason=k.get("reason"),
            )
            for k in data.get("keys", [])
        ]
        self.current_index = data.get("current_index", 0)
        self.last_failed_key = data.get("last_failed_key")


class KeySelector:
    def __init__(
        self,
        keys: list[KeyState],
        index: int = 0,
        last_failed_key: str | None = None,
        max_concurrent_streams_per_key: int = 2,
    ):
        self.keys = keys
        self.index = index % len(keys) if keys else 0
        self.last_failed_key = last_failed_key
        self.last_used_key: str | None = None
        self.max_concurrent_streams_per_key = max_concurrent_streams_per_key
        self._lock = Lock()

    def select(self) -> KeyState | None:
        with self._lock:
            if not self.keys:
                return None

            candidates = [k for k in self.keys if k.is_available()]
            if not candidates:
                return None

            selected = self._smart_pick(candidates)
            self.index = self.keys.index(selected)
            return selected

    def _smart_pick(self, candidates: list[KeyState]) -> KeyState:
        if len(candidates) == 1:
            return candidates[0]

        keys = list(candidates)

        # Fisher-Yates shuffle
        for i in range(len(keys) - 1, 0, -1):
            j = random.randint(0, i)
            keys[i], keys[j] = keys[j], keys[i]

        # Move last failed key to end if present
        if self.last_failed_key:
            for i, k in enumerate(keys):
                if k.key == self.last_failed_key:
                    keys.append(keys.pop(i))
                    break

        return keys[0]

    def mark_cooldown(self, key: str, cooldown_hours: int, reason: str):
        from datetime import timedelta

        with self._lock:
            for k in self.keys:
                if k.key == key:
                    k.status = KeyStatus.COOLDOWN
                    k.cooldown_until = datetime.now(timezone.utc) + timedelta(
                        hours=cooldown_hours
                    )
                    k.reason = reason
                    break

    def mark_disabled(self, key: str, reason: str):
        with self._lock:
            for k in self.keys:
                if k.key == key:
                    k.status = KeyStatus.DISABLED
                    k.cooldown_until = None
                    k.reason = reason
                    break

    def update_last_failed_key(self, key: str | None):
        with self._lock:
            self.last_failed_key = key

    def acquire_stream_lease(self) -> KeyState | None:
        with self._lock:
            candidates = [
                k
                for k in self.keys
                if k.is_available()
                and k.active_streams < self.max_concurrent_streams_per_key
            ]
            if not candidates:
                return None

            min_load = min(k.active_streams for k in candidates)
            lowest_load = [k for k in candidates if k.active_streams == min_load]
            selected = self._smart_pick(lowest_load)
            selected.active_streams += 1
            self.index = self.keys.index(selected)
            return selected

    def release_stream_lease(self, key: str) -> None:
        with self._lock:
            for item in self.keys:
                if item.key == key:
                    item.active_streams = max(0, item.active_streams - 1)
                    break

    def get_active_streams(self, key: str) -> int:
        with self._lock:
            for item in self.keys:
                if item.key == key:
                    return item.active_streams
            return 0
