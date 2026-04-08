from dataclasses import dataclass

import httpx


@dataclass
class CooldownInfo:
    hours: int
    reason: str


class RateLimitHandler:
    """Detects rate limit and usage limit responses from ollama.com.

    Ollama.com has three types of limits:
    - Session limit: resets every 5 hours (per-plan GPU time quota)
    - Weekly limit: resets every 7 days
    - Rate limit: short-term request frequency limit (429)

    Usage limit exhaustion returns 402 with error code "usage_limit_upgrade".
    Rate limit returns 429 with "rate limit exceeded".
    Weekly usage limit returns 429 with "weekly usage limit".
    """

    def __init__(
        self,
        cooldown_session_hours: int = 5,
        cooldown_weekly_hours: int = 168,
        cooldown_rate_hours: int = 4,
    ):
        self.cooldown_session_hours = cooldown_session_hours
        self.cooldown_weekly_hours = cooldown_weekly_hours
        self.cooldown_rate_hours = cooldown_rate_hours

    def detect_cooldown(self, response: httpx.Response) -> CooldownInfo | None:
        status = response.status_code

        # 402: Usage limit exhausted (plan quota)
        if status == 402:
            return self._detect_usage_limit(response)

        # 429: Rate limit or weekly usage limit
        if status == 429:
            return self._detect_rate_limit(response)

        return None

    def _detect_usage_limit(self, response: httpx.Response) -> CooldownInfo:
        """Handle 402 Payment Required - usage limit exhausted."""
        try:
            error_data = response.json()
            error_message = error_data.get("error", "")
        except Exception:
            error_message = ""

        error_lower = error_message.lower()

        # Weekly usage limit
        if "weekly" in error_lower:
            return CooldownInfo(
                hours=self.cooldown_weekly_hours,
                reason="weekly_usage_limit",
            )

        # General usage limit (session-level)
        return CooldownInfo(
            hours=self.cooldown_session_hours,
            reason="usage_limit",
        )

    def _detect_rate_limit(self, response: httpx.Response) -> CooldownInfo:
        """Handle 429 Too Many Requests."""
        try:
            error_data = response.json()
            error_message = error_data.get("error", "")
        except Exception:
            error_message = ""

        error_lower = error_message.lower()

        # Weekly usage limit (also returns 429 in some cases)
        if "weekly usage limit" in error_lower or "weekly" in error_lower:
            return CooldownInfo(
                hours=self.cooldown_weekly_hours,
                reason="weekly_usage_limit",
            )

        # Session usage limit
        if "session usage limit" in error_lower or "usage limit" in error_lower:
            return CooldownInfo(
                hours=self.cooldown_session_hours,
                reason="session_usage_limit",
            )

        # Standard rate limit
        if "rate limit" in error_lower or "too many requests" in error_lower:
            return CooldownInfo(
                hours=self.cooldown_rate_hours,
                reason="rate_limit",
            )

        # Unknown 429 - treat as session limit (conservative)
        return CooldownInfo(hours=self.cooldown_session_hours, reason="unknown")
