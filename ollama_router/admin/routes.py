# pyright: reportMissingImports=false

import asyncio
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.security import OAuth2PasswordRequestForm

from ollama_router.admin.auth import create_session
from ollama_router.admin.logs import filter_logs, parse_log_line, read_log_file
from ollama_router.admin.middleware import get_current_user
from ollama_router.admin.views import _build_keys, _build_requests, _build_stats
from ollama_router.config import Config, get_key_id
from ollama_router.state import KeySelector, KeyState, KeyStatus, StateStore


def _is_htmx(request: Request) -> bool:
    return request.headers.get("hx-request") == "true"


def create_admin_api_router() -> APIRouter:
    router = APIRouter(prefix="/admin/api", tags=["admin-api"])

    @router.post("/login")
    async def login(
        request: Request,
        response: Response,
        form: OAuth2PasswordRequestForm = Depends(),
    ) -> dict[str, str | bool]:
        config: Config = request.app.state.config
        if (
            form.username != config.admin_username
            or form.password != config.admin_password
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )

        token = create_session(form.username, config.admin_session_secret)
        response.set_cookie(
            key="admin_session",
            value=token,
            httponly=True,
            samesite="lax",
            max_age=86400,
            path="/",
        )
        return {"ok": True, "username": form.username}

    @router.post("/logout")
    async def logout(
        response: Response, _: str = Depends(get_current_user)
    ) -> dict[str, bool]:
        response.delete_cookie("admin_session", path="/")
        return {"ok": True}

    @router.get("/stats/panel", response_class=HTMLResponse)
    async def stats_panel(
        request: Request, _: str = Depends(get_current_user)
    ) -> Response:
        templates = request.app.state.templates
        selector: KeySelector = request.app.state.selector
        history = request.app.state.request_history
        return templates.TemplateResponse(
            request=request,
            name="admin/_stats_panel.html",
            context={"stats": _build_stats(selector, history)},
        )

    @router.get("/keys/table", response_class=HTMLResponse)
    async def keys_table(
        request: Request, _: str = Depends(get_current_user)
    ) -> Response:
        templates = request.app.state.templates
        selector: KeySelector = request.app.state.selector
        return templates.TemplateResponse(
            request=request,
            name="admin/_keys_table.html",
            context={"keys": _build_keys(selector)},
        )

    @router.get("/history/table", response_class=HTMLResponse)
    async def history_table(
        request: Request, _: str = Depends(get_current_user)
    ) -> Response:
        templates = request.app.state.templates
        history = request.app.state.request_history
        return templates.TemplateResponse(
            request=request,
            name="admin/_history_table.html",
            context={"requests": _build_requests(history)},
        )

    @router.get("/keys")
    async def list_keys(
        request: Request, _: str = Depends(get_current_user)
    ) -> dict[str, list[dict] | int]:
        selector: KeySelector = request.app.state.selector
        now = datetime.now(timezone.utc)
        keys: list[dict] = []
        for key_state in selector.keys:
            cooldown_until = (
                key_state.cooldown_until.isoformat()
                if key_state.cooldown_until
                else None
            )
            remaining = None
            if key_state.cooldown_until:
                remaining = max(
                    0, int((key_state.cooldown_until - now).total_seconds())
                )
            keys.append(
                {
                    "key_id": get_key_id(key_state.key),
                    "status": key_state.status.value,
                    "cooldown_until": cooldown_until,
                    "cooldown_remaining_seconds": remaining,
                    "reason": key_state.reason,
                    "is_available": key_state.is_available(),
                }
            )
        return {"items": keys, "total": len(keys)}

    @router.post("/keys")
    async def add_key(
        request: Request,
        key: str = Form(""),
        _: str = Depends(get_current_user),
    ) -> Response:
        config: Config = request.app.state.config
        selector: KeySelector = request.app.state.selector
        state_store: StateStore = request.app.state.state_store

        key = key.strip()
        if not key:
            raise HTTPException(status_code=400, detail="Key cannot be empty")
        if any(item.key == key for item in selector.keys):
            raise HTTPException(status_code=409, detail="Key already exists")

        config.keys.append(key)
        selector.keys.append(KeyState(key=key))
        state_store.keys = selector.keys
        state_store.current_index = selector.index
        state_store.save()

        if _is_htmx(request):
            return Response(status_code=200, headers={"HX-Redirect": "/admin/keys"})
        return {"ok": True, "key_id": get_key_id(key)}

    @router.delete("/keys/{key_id}")
    async def remove_key(
        key_id: str,
        request: Request,
        _: str = Depends(get_current_user),
    ) -> Response:
        config: Config = request.app.state.config
        selector: KeySelector = request.app.state.selector
        state_store: StateStore = request.app.state.state_store

        target_index = -1
        target_key = ""
        for idx, key_state in enumerate(selector.keys):
            if get_key_id(key_state.key) == key_id:
                target_index = idx
                target_key = key_state.key
                break

        if target_index < 0:
            raise HTTPException(status_code=404, detail="Key not found")

        selector.keys.pop(target_index)
        config.keys = [k for k in config.keys if k != target_key]
        state_store.keys = selector.keys
        if selector.keys:
            selector.index = selector.index % len(selector.keys)
        else:
            selector.index = 0
        state_store.current_index = selector.index
        state_store.save()

        if _is_htmx(request):
            return Response(status_code=200, headers={"HX-Redirect": "/admin/keys"})
        return {"ok": True, "key_id": key_id}

    @router.post("/keys/{key_id}/reset")
    async def reset_key(
        key_id: str,
        request: Request,
        _: str = Depends(get_current_user),
    ) -> Response:
        selector: KeySelector = request.app.state.selector
        state_store: StateStore = request.app.state.state_store
        for key_state in selector.keys:
            if get_key_id(key_state.key) == key_id:
                key_state.status = KeyStatus.AVAILABLE
                key_state.cooldown_until = None
                key_state.reason = None
                state_store.current_index = selector.index
                state_store.save()
                if _is_htmx(request):
                    return Response(
                        status_code=200, headers={"HX-Redirect": "/admin/keys"}
                    )
                return {"ok": True, "key_id": key_id}

        raise HTTPException(status_code=404, detail="Key not found")

    @router.post("/keys/{key_id}/disable")
    async def disable_key(
        key_id: str,
        request: Request,
        _: str = Depends(get_current_user),
    ) -> Response:
        selector: KeySelector = request.app.state.selector
        state_store: StateStore = request.app.state.state_store
        for key_state in selector.keys:
            if get_key_id(key_state.key) == key_id:
                selector.mark_disabled(key_state.key, reason="admin_disabled")
                state_store.current_index = selector.index
                state_store.last_failed_key = selector.last_failed_key
                state_store.save()
                if _is_htmx(request):
                    return Response(
                        status_code=200, headers={"HX-Redirect": "/admin/keys"}
                    )
                return {"ok": True, "key_id": key_id}

        raise HTTPException(status_code=404, detail="Key not found")

    @router.get("/stats")
    async def stats(
        request: Request, _: str = Depends(get_current_user)
    ) -> dict[str, int | float | dict[str, int]]:
        selector: KeySelector = request.app.state.selector
        history = request.app.state.request_history

        status_counter: Counter[int] = Counter(item["status_code"] for item in history)
        key_counter: Counter[str] = Counter(
            item["key_id"] for item in history if item["key_id"]
        )
        total = len(history)
        avg_latency = 0.0
        if total:
            avg_latency = sum(float(item["latency"]) for item in history) / total

        return {
            "available_keys": sum(1 for k in selector.keys if k.is_available()),
            "total_keys": len(selector.keys),
            "history_size": total,
            "average_latency_ms": round(avg_latency, 2),
            "requests_by_status": {str(k): v for k, v in status_counter.items()},
            "requests_by_key": dict(key_counter),
        }

    @router.get("/history")
    async def history(
        request: Request, _: str = Depends(get_current_user)
    ) -> dict[str, list[dict] | int]:
        history_records = list(request.app.state.request_history)
        return {"items": history_records, "total": len(history_records)}

    HEARTBEAT_INTERVAL = 30  # seconds

    @router.get("/logs")
    async def get_logs(
        request: Request,
        start: str | None = None,
        end: str | None = None,
        levels: str = "",
        offset: int = 0,
        limit: int = 1000,
        _: str = Depends(get_current_user),
    ) -> dict:
        """Get historical logs with filtering and pagination."""
        from pathlib import Path
        from datetime import datetime

        config: Config = request.app.state.config

        # Return empty if no logging configured
        if not config.logging.file:
            return {
                "items": [],
                "total": 0,
                "filtered": 0,
                "offset": offset,
                "limit": limit,
                "has_more": False,
            }

        log_path = Path(config.logging.file)

        if not log_path.exists():
            return {
                "items": [],
                "total": 0,
                "filtered": 0,
                "offset": offset,
                "limit": limit,
                "has_more": False,
            }

        # Parse time range (convert to naive datetime for comparison)
        start_dt = None
        end_dt = None
        if start:
            try:
                dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                start_dt = dt.replace(tzinfo=None) if dt.tzinfo else dt
            except ValueError:
                pass
        if end:
            try:
                dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
                end_dt = dt.replace(tzinfo=None) if dt.tzinfo else dt
            except ValueError:
                pass

        # Parse levels
        level_set = None
        if levels:
            level_set = set(levels.split(",")) & {
                "DEBUG",
                "INFO",
                "WARNING",
                "ERROR",
                "CRITICAL",
            }
            if not level_set:
                level_set = None

        # Read and filter logs
        entries = read_log_file(log_path)
        filtered, total, has_more = filter_logs(
            entries, start_dt, end_dt, level_set, offset, limit
        )

        return {
            "items": [e.to_dict() for e in filtered],
            "total": total,
            "filtered": len(filtered),
            "offset": offset,
            "limit": limit,
            "has_more": has_more,
        }

    @router.get("/logs/stream")
    async def log_stream(
        request: Request,
        levels: str = "",
        _: str = Depends(get_current_user),
    ):
        """SSE endpoint for real-time logs."""
        import asyncio
        from pathlib import Path

        config: Config = request.app.state.config

        # Return error if no logging configured
        if not config.logging.file:

            async def error_generator():
                yield f"event: error\ndata: {json.dumps({'error': 'Logging not configured'})}\n\n"

            return StreamingResponse(error_generator(), media_type="text/event-stream")

        log_path = Path(config.logging.file)
        level_set = (
            set(levels.split(",")) & {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
            if levels
            else None
        )

        if not log_path.exists():

            async def error_generator():
                yield f"event: error\ndata: {json.dumps({'error': 'Log file not found'})}\n\n"

            return StreamingResponse(error_generator(), media_type="text/event-stream")

        async def event_generator():
            try:
                async with aiofiles.open(log_path, encoding="utf-8") as f:
                    await f.seek(0, 2)  # Seek to end
                    last_heartbeat = asyncio.get_event_loop().time()

                    while True:
                        # Check client disconnect
                        if await request.is_disconnected():
                            break

                        # Send heartbeat
                        now = asyncio.get_event_loop().time()
                        if now - last_heartbeat >= HEARTBEAT_INTERVAL:
                            yield "event: ping\ndata: {}\n\n"
                            last_heartbeat = now

                        line = await f.readline()
                        if line:
                            entry = parse_log_line(line.strip())
                            if entry and (not level_set or entry.level in level_set):
                                yield f"event: log\ndata: {json.dumps(entry.to_dict())}\n\n"
                        else:
                            await asyncio.sleep(0.1)
            except Exception as e:
                yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
        )

    @router.get("/logs/download")
    async def download_logs(
        request: Request,
        start: str | None = None,
        end: str | None = None,
        levels: str = "",
        format: str = "log",
        _: str = Depends(get_current_user),
    ) -> Response:
        """Download filtered logs as .log or .json file."""
        from pathlib import Path
        from datetime import datetime

        config: Config = request.app.state.config

        # Return 404 if no logging configured
        if not config.logging.file:
            raise HTTPException(status_code=404, detail="Logging not configured")

        log_path = Path(config.logging.file)

        if not log_path.exists():
            raise HTTPException(status_code=404, detail="Log file not found")

        # Parse time range (convert to naive datetime for comparison)
        start_dt = None
        end_dt = None
        if start:
            try:
                dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                start_dt = dt.replace(tzinfo=None) if dt.tzinfo else dt
            except ValueError:
                pass
        if end:
            try:
                dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
                end_dt = dt.replace(tzinfo=None) if dt.tzinfo else dt
            except ValueError:
                pass

        # Parse levels
        level_set = None
        if levels:
            level_set = set(levels.split(",")) & {
                "DEBUG",
                "INFO",
                "WARNING",
                "ERROR",
                "CRITICAL",
            }
            if not level_set:
                level_set = None

        # Read and filter logs
        entries = read_log_file(log_path)
        filtered, _, _ = filter_logs(entries, start_dt, end_dt, level_set, 0, 10000)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if format == "json":
            content = json.dumps(
                [e.to_dict() for e in filtered], indent=2, ensure_ascii=False
            )
            return Response(
                content=content,
                media_type="application/json",
                headers={
                    "Content-Disposition": f"attachment; filename=logs_{timestamp}.json"
                },
            )
        else:
            # Default to .log format
            lines = []
            for e in filtered:
                ts = e.timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                lines.append(f"{ts} {e.level} [{e.request_id}] {e.message}")
            content = "\n".join(lines)
            return Response(
                content=content,
                media_type="text/plain",
                headers={
                    "Content-Disposition": f"attachment; filename=logs_{timestamp}.log"
                },
            )

    return router
