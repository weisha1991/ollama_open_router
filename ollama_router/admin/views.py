# pyright: reportMissingImports=false

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from ollama_router.admin.middleware import get_current_user
from ollama_router.config import get_key_id
from ollama_router.state import KeySelector


def _build_stats(selector: KeySelector, history) -> dict:
    available = sum(1 for k in selector.keys if k.is_available())
    return {
        "total_keys": len(selector.keys),
        "available_keys": available,
        "cooldown_keys": len(selector.keys) - available,
        "total_requests": len(history),
    }


def _build_keys(selector: KeySelector) -> list[dict]:
    now = datetime.now(timezone.utc)
    keys = []
    for k in selector.keys:
        remaining = None
        if k.cooldown_until:
            remaining = max(0, int((k.cooldown_until - now).total_seconds()))
        keys.append(
            {
                "id": get_key_id(k.key),
                "masked_key": f"...{k.key[-4:]}" if len(k.key) > 4 else "***",
                "status": k.status.value,
                "cooldown_until": k.cooldown_until.isoformat()
                if k.cooldown_until
                else None,
                "cooldown_remaining_seconds": remaining,
                "reason": k.reason,
            }
        )
    return keys


def _build_requests(history) -> list[dict]:
    # Support both RequestHistory object and legacy deque
    if hasattr(history, 'get_all'):
        records = history.get_all()
        return [
            {
                "time": r.timestamp.isoformat() if hasattr(r, 'timestamp') else r.get("timestamp", "-"),
                "method": r.method if hasattr(r, 'method') else r.get("method", "-"),
                "path": r.path if hasattr(r, 'path') else r.get("path", "-"),
                "status": r.status_code if hasattr(r, 'status_code') else r.get("status_code", 0),
                "key_id": r.key_id if hasattr(r, 'key_id') else r.get("key_id", "-"),
                "latency": r.latency_ms if hasattr(r, 'latency_ms') else r.get("latency_ms", r.get("latency", 0)),
            }
            for r in reversed(records)
        ]
    else:
        # Legacy deque format
        return [
            {
                "time": r.get("timestamp", "-"),
                "method": r.get("method", "-"),
                "path": r.get("path", "-"),
                "status": r.get("status_code", 0),
                "key_id": r.get("key_id", "-"),
                "latency": r.get("latency_ms", r.get("latency", 0)),
            }
            for r in reversed(list(history))
        ]


def create_admin_views_router() -> APIRouter:
    router = APIRouter(tags=["admin-views"])

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
        return templates.TemplateResponse(
            request=request,
            name="admin/dashboard.html",
            context={
                "title": "Dashboard",
                "username": username,
                "stats": _build_stats(selector, history),
            },
        )

    @router.get("/admin/keys")
    async def admin_keys_page(
        request: Request,
        username: str = Depends(get_current_user),
    ) -> Response:
        templates: Jinja2Templates = request.app.state.templates
        selector: KeySelector = request.app.state.selector
        return templates.TemplateResponse(
            request=request,
            name="admin/keys.html",
            context={
                "title": "Keys",
                "username": username,
                "keys": _build_keys(selector),
            },
        )

    @router.get("/admin/history")
    async def admin_history_page(
        request: Request,
        username: str = Depends(get_current_user),
    ) -> Response:
        templates: Jinja2Templates = request.app.state.templates
        history = request.app.state.request_history
        return templates.TemplateResponse(
            request=request,
            name="admin/history.html",
            context={
                "title": "History",
                "username": username,
                "requests": _build_requests(history),
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
