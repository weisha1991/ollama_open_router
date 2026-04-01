from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
from pathlib import Path


class KeyStatus(Enum):
    AVAILABLE = "available"
    COOLDOWN = "cooldown"


@dataclass
class KeyState:
    key: str
    status: KeyStatus = KeyStatus.AVAILABLE
    cooldown_until: datetime | None = None
    reason: str | None = None

    def is_available(self) -> bool:
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


class KeySelector:
    def __init__(self, keys: list[KeyState]):
        self.keys = keys
        self.index = 0

    def select(self) -> KeyState | None:
        if not self.keys:
            return None

        start_index = self.index % len(self.keys)
        for i in range(len(self.keys)):
            idx = (start_index + i) % len(self.keys)
            if self.keys[idx].is_available():
                self.index = (idx + 1) % len(self.keys)
                return self.keys[idx]

        return None

    def mark_cooldown(self, key: str, cooldown_hours: int, reason: str):
        from datetime import timedelta

        for k in self.keys:
            if k.key == key:
                k.status = KeyStatus.COOLDOWN
                k.cooldown_until = datetime.now(timezone.utc) + timedelta(
                    hours=cooldown_hours
                )
                k.reason = reason
                break
