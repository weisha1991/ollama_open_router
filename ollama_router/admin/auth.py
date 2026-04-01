import base64
import hashlib
import hmac
import time


def _sign(payload: str, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256)
    return digest.hexdigest()


def create_session(username: str, secret: str, ttl_seconds: int = 86400) -> str:
    expires_at = int(time.time()) + ttl_seconds
    raw_payload = f"{username}:{expires_at}"
    payload_b64 = base64.urlsafe_b64encode(raw_payload.encode("utf-8")).decode("utf-8")
    signature = _sign(payload_b64, secret)
    return f"{payload_b64}.{signature}"


def validate_session(session_token: str | None, secret: str) -> str | None:
    if not session_token:
        return None

    try:
        payload_b64, signature = session_token.split(".", 1)
    except ValueError:
        return None

    expected_signature = _sign(payload_b64, secret)
    if not hmac.compare_digest(signature, expected_signature):
        return None

    try:
        raw_payload = base64.urlsafe_b64decode(payload_b64.encode("utf-8")).decode(
            "utf-8"
        )
        username, expires_raw = raw_payload.rsplit(":", 1)
        expires_at = int(expires_raw)
    except Exception:
        return None

    if int(time.time()) > expires_at:
        return None

    return username
