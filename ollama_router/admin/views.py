# pyright: reportMissingImports=false

from collections import Counter
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from ollama_router.admin.middleware import get_current_user
from ollama_router.config import get_key_id
from ollama_router.state import KeySelector, KeyStatus


def _format_timestamp_display(value: str | None) -> str:
    if not value or value == "-":
        return "-"
    normalized = value.replace("Z", "+00:00")
    try:
        timestamp = datetime.fromisoformat(normalized)
    except ValueError:
        return value
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _format_timestamp_short(value: str | None) -> str:
    if not value or value == "-":
        return "-"
    normalized = value.replace("Z", "+00:00")
    try:
        timestamp = datetime.fromisoformat(normalized)
    except ValueError:
        return value
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc).strftime("%H:%M:%S")


def _format_remaining_seconds(seconds: int | None) -> str:
    if seconds is None or seconds <= 0:
        return "Ready"

    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m remaining"
    if minutes:
        return f"{minutes}m {secs:02d}s remaining"
    return f"{secs}s remaining"


def _build_stats(selector: KeySelector, history) -> dict:
    available = sum(1 for k in selector.keys if k.is_available())
    disabled = sum(1 for k in selector.keys if k.status == KeyStatus.DISABLED)
    cooldown = sum(1 for k in selector.keys if k.status == KeyStatus.COOLDOWN)
    return {
        "total_keys": len(selector.keys),
        "available_keys": available,
        "cooldown_keys": cooldown,
        "disabled_keys": disabled,
        "total_requests": len(history),
    }


def _build_keys(selector: KeySelector) -> list[dict]:
    now = datetime.now(timezone.utc)
    last_used_key_id = (
        get_key_id(selector.last_used_key) if selector.last_used_key else None
    )
    keys = []
    for k in selector.keys:
        remaining = None
        if k.cooldown_until:
            remaining = max(0, int((k.cooldown_until - now).total_seconds()))
        key_id = get_key_id(k.key)
        cooldown_until = k.cooldown_until.isoformat() if k.cooldown_until else None
        cooldown_label = "Ready"
        if k.status == KeyStatus.COOLDOWN:
            cooldown_label = _format_remaining_seconds(remaining)
        elif k.status == KeyStatus.DISABLED:
            cooldown_label = "Disabled"
        keys.append(
            {
                "id": key_id,
                "masked_key": f"...{k.key[-4:]}" if len(k.key) > 4 else "***",
                "status": k.status.value,
                "cooldown_until": cooldown_until,
                "cooldown_until_display": _format_timestamp_display(cooldown_until),
                "cooldown_remaining_seconds": remaining,
                "cooldown_label": cooldown_label,
                "reason": k.reason,
                "is_last_used": key_id == last_used_key_id,
            }
        )
    return keys


def _build_requests(history) -> list[dict]:
    # Support both RequestHistory object and legacy deque
    if hasattr(history, "get_all"):
        records = history.get_all()
        items = []
        for record in reversed(records):
            time_value = (
                record.timestamp.isoformat()
                if hasattr(record, "timestamp")
                else record.get("timestamp", "-")
            )
            items.append(
                {
                    "time": time_value,
                    "display_time": _format_timestamp_display(time_value),
                    "time_short": _format_timestamp_short(time_value),
                    "request_id": record.request_id
                    if hasattr(record, "request_id")
                    else record.get("request_id", "-"),
                    "method": record.method
                    if hasattr(record, "method")
                    else record.get("method", "-"),
                    "path": record.path if hasattr(record, "path") else record.get("path", "-"),
                    "status": record.status_code
                    if hasattr(record, "status_code")
                    else record.get("status_code", 0),
                    "key_id": record.key_id
                    if hasattr(record, "key_id")
                    else record.get("key_id", "-"),
                    "latency": record.latency_ms
                    if hasattr(record, "latency_ms")
                    else record.get("latency_ms", record.get("latency", 0)),
                }
            )
        return items
    else:
        # Legacy deque format
        items = []
        for record in reversed(list(history)):
            time_value = record.get("timestamp", "-")
            items.append(
                {
                    "time": time_value,
                    "display_time": _format_timestamp_display(time_value),
                    "time_short": _format_timestamp_short(time_value),
                    "request_id": record.get("request_id", "-"),
                    "method": record.get("method", "-"),
                    "path": record.get("path", "-"),
                    "status": record.get("status_code", 0),
                    "key_id": record.get("key_id", "-"),
                    "latency": record.get("latency_ms", record.get("latency", 0)),
                }
            )
        return items


def _build_request_overview(requests: list[dict], limit: int = 24) -> list[dict]:
    buckets: dict[str, int] = {}
    for request in reversed(requests[:limit]):
        time_value = request.get("time", "")
        label = "--:--"
        if isinstance(time_value, str) and len(time_value) >= 16:
            label = time_value[11:16]
        buckets[label] = buckets.get(label, 0) + 1
    items = [{"label": label, "count": count} for label, count in buckets.items()]
    if not items:
        return items

    width = 520
    height = 130
    max_count = max(item["count"] for item in items) or 1
    step = width / max(len(items) - 1, 1)
    for index, item in enumerate(items):
        item["x"] = round(index * step, 2)
        item["y"] = round(height - ((item["count"] / max_count) * (height - 16)), 2)
    return items


def _build_recent_activity(requests: list[dict], limit: int = 5) -> list[dict]:
    activity = []
    for request in requests[:limit]:
        status = int(request.get("status", 0))
        path = request.get("path", "-")
        method = request.get("method", "-")
        label = f"{method} {path}"
        activity.append(
            {
                "request_id": request.get("request_id", "-"),
                "label": label,
                "status": status,
                "path": path,
                "method": method,
                "key_id": request.get("key_id", "-"),
                "latency": request.get("latency", 0),
                "display_time": request.get("display_time", "-"),
                "time_short": request.get("time_short", "-"),
            }
        )
    return activity


def _build_dashboard_context(selector: KeySelector, history) -> dict:
    stats = _build_stats(selector, history)
    keys = _build_keys(selector)
    requests = _build_requests(history)
    recent_activity = _build_recent_activity(requests)
    request_overview = _build_request_overview(requests)
    request_summary = {
        "bucket_count": len(request_overview),
        "total": sum(item["count"] for item in request_overview),
        "peak": max((item["count"] for item in request_overview), default=0),
        "latest": request_overview[-1]["count"] if request_overview else 0,
        "latest_label": request_overview[-1]["label"] if request_overview else "--:--",
        "state": (
            "empty"
            if not request_overview
            else "single"
            if len(request_overview) == 1
            else "ready"
        ),
    }
    status_counts = Counter(
        item["status"] for item in recent_activity if item["status"]
    )
    return {
        "stats": stats,
        "distribution": {
            "available": stats["available_keys"],
            "cooldown": stats["cooldown_keys"],
            "disabled": stats["disabled_keys"],
        },
        "request_overview": request_overview,
        "request_summary": request_summary,
        "recent_keys": keys[:5],
        "recent_activity": recent_activity,
        "status_counts": dict(status_counts),
    }


def _build_history_summary(requests: list[dict]) -> dict:
    total = len(requests)
    success = sum(1 for item in requests if 200 <= int(item.get("status", 0)) < 300)
    client_errors = sum(
        1 for item in requests if 400 <= int(item.get("status", 0)) < 500
    )
    avg_latency = 0
    if total:
        avg_latency = round(
            sum(float(item.get("latency", 0)) for item in requests) / total
        )
    return {
        "total": total,
        "success": success,
        "client_errors": client_errors,
        "avg_latency": avg_latency,
    }


def create_admin_views_router() -> APIRouter:
    router = APIRouter(tags=["admin-views"])

    @router.get("/admin")
    @router.get("/admin/")
    async def admin_root() -> RedirectResponse:
        return RedirectResponse(url="/admin/dashboard", status_code=302)

    @router.get("/admin/login")
    async def admin_login_page(request: Request) -> Response:
        templates: Jinja2Templates = request.app.state.templates
        return templates.TemplateResponse(
            request=request,
            name="admin/login.html",
            context={"title": "Admin Login"},
        )

    @router.get("/admin/dashboard")
    async def admin_dashboard_page(
        request: Request,
        username: str = Depends(get_current_user),
    ) -> Response:
        templates: Jinja2Templates = request.app.state.templates
        selector: KeySelector = request.app.state.selector
        history = request.app.state.request_history
        dashboard = _build_dashboard_context(selector, history)
        return templates.TemplateResponse(
            request=request,
            name="admin/dashboard.html",
            context={
                "title": "Dashboard",
                "username": username,
                "stats": dashboard["stats"],
                "dashboard": dashboard,
            },
        )

    @router.get("/admin/keys")
    async def admin_keys_page(
        request: Request,
        username: str = Depends(get_current_user),
    ) -> Response:
        templates: Jinja2Templates = request.app.state.templates
        selector: KeySelector = request.app.state.selector
        history = request.app.state.request_history
        return templates.TemplateResponse(
            request=request,
            name="admin/keys.html",
            context={
                "title": "Keys",
                "username": username,
                "keys": _build_keys(selector),
                "stats": _build_stats(selector, history),
            },
        )

    @router.get("/admin/history")
    async def admin_history_page(
        request: Request,
        username: str = Depends(get_current_user),
    ) -> Response:
        templates: Jinja2Templates = request.app.state.templates
        history = request.app.state.request_history
        requests = _build_requests(history)
        return templates.TemplateResponse(
            request=request,
            name="admin/history.html",
            context={
                "title": "History",
                "username": username,
                "requests": requests,
                "history_summary": _build_history_summary(requests),
            },
        )

    @router.get("/admin/logs")
    async def admin_logs_page(
        request: Request,
        username: str = Depends(get_current_user),
    ) -> Response:
        templates: Jinja2Templates = request.app.state.templates
        return templates.TemplateResponse(
            request=request,
            name="admin/logs.html",
            context={
                "title": "Logs",
                "username": username,
            },
        )

    return router
