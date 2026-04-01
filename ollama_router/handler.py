from dataclasses import dataclass

import httpx


@dataclass
class CooldownInfo:
    hours: int
    reason: str


class RateLimitHandler:
    def __init__(self, cooldown_session_hours: int = 72, cooldown_rate_hours: int = 4):
        self.cooldown_session_hours = cooldown_session_hours
        self.cooldown_rate_hours = cooldown_rate_hours

    def detect_cooldown(self, response: httpx.Response) -> CooldownInfo | None:
        if response.status_code != 429:
            return None

        try:
            error_data = response.json()
            error_message = error_data.get("error", "")
        except Exception:
            error_message = ""

        error_lower = error_message.lower()

        if "session usage limit" in error_lower:
            return CooldownInfo(
                hours=self.cooldown_session_hours,
                reason="session_usage_limit",
            )

        if "rate limit" in error_lower or "too many requests" in error_lower:
            return CooldownInfo(
                hours=self.cooldown_rate_hours,
                reason="rate_limit",
            )

        return CooldownInfo(hours=self.cooldown_session_hours, reason="unknown")
