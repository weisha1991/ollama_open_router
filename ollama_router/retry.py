"""Retry management with key switching and error handling."""

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import httpx

from ollama_router.config import get_key_id
from ollama_router.handler import CooldownInfo, KeyAction, RateLimitHandler
from ollama_router.request_history import RequestHistory, RequestRecord
from ollama_router.state import KeySelector, KeyState, StateStore

if TYPE_CHECKING:
    from ollama_router.proxy import ProxyClient

logger = logging.getLogger("ollama_router")

MAX_RETRIES = 3


@dataclass
class RetryResult:
    """Result of retry execution."""

    response: httpx.Response | None
    success: bool
    attempts: int
    last_error: str | None = None


@dataclass
class StreamSetupResult:
    """Prepared streaming result before downstream bytes are emitted."""

    success: bool
    attempts: int
    response: httpx.Response | None = None
    stream_context: Any | None = None
    selected_key: KeyState | None = None
    first_chunk: bytes | None = None
    chunk_iterator: Any | None = None
    error_status_code: int | None = None
    error_body: bytes | None = None
    error_headers: dict[str, str] | None = None
    last_error: str | None = None


class RetryManager:
    """Handles retry loop with key switching and error handling."""

    def __init__(
        self,
        selector: KeySelector,
        handler: RateLimitHandler,
        state_store: StateStore,
        history: RequestHistory,
    ):
        self.selector = selector
        self.handler = handler
        self.state_store = state_store
        self.history = history

    def _sync_and_save(self):
        """Sync selector state to state store and persist."""
        self.state_store.current_index = self.selector.index
        self.state_store.last_failed_key = self.selector.last_failed_key
        self.state_store.save()

    async def execute_with_retry(
        self,
        method: str,
        path: str,
        headers: dict,
        body: dict | None,
        proxy: "ProxyClient",
        request_id: str,
    ) -> RetryResult:
        """Execute request with retry logic."""
        for attempt in range(MAX_RETRIES):
            selected_key = self.selector.select()
            if selected_key is None:
                logger.warning("all_keys_exhausted path=%s", path)
                return RetryResult(
                    response=None,
                    success=False,
                    attempts=attempt,
                    last_error="No available API keys",
                )

            headers["Authorization"] = f"Bearer {selected_key.key}"
            start_ts = time.perf_counter()

            try:
                response = await proxy.forward(
                    method=method,
                    path=path,
                    headers=headers,
                    json_data=body,
                )
            except Exception as e:
                latency = round((time.perf_counter() - start_ts) * 1000, 2)
                key_id = get_key_id(selected_key.key)
                logger.error(
                    "proxy_error key_id=%s path=%s attempt=%d/%d error_type=%s error=%r latency=%.2fms",
                    key_id,
                    path,
                    attempt + 1,
                    MAX_RETRIES,
                    type(e).__name__,
                    e,
                    latency,
                )
                self._record_request(
                    request_id=request_id,
                    method=method,
                    path=path,
                    status_code=502,
                    key_id=key_id,
                    latency=latency,
                )
                return RetryResult(
                    response=None,
                    success=False,
                    attempts=attempt + 1,
                    last_error=str(e),
                )

            latency = round((time.perf_counter() - start_ts) * 1000, 2)

            # Check for rate limit / auth error
            cooldown_info = self.handler.detect_cooldown(response)
            if cooldown_info:
                if cooldown_info.action == KeyAction.DISABLE:
                    self.selector.mark_disabled(
                        selected_key.key,
                        cooldown_info.reason,
                    )
                    self.selector.update_last_failed_key(selected_key.key)
                    self._sync_and_save()
                    logger.warning(
                        "key_disabled key_id=%s reason=%s attempt=%d/%d",
                        get_key_id(selected_key.key),
                        cooldown_info.reason,
                        attempt + 1,
                        MAX_RETRIES,
                    )
                    if attempt < MAX_RETRIES - 1:
                        continue

                    self._record_request(
                        request_id=request_id,
                        method=method,
                        path=path,
                        status_code=response.status_code,
                        key_id=get_key_id(selected_key.key),
                        latency=latency,
                    )
                    return RetryResult(
                        response=response,
                        success=False,
                        attempts=attempt + 1,
                        last_error=f"Key disabled: {cooldown_info.reason}",
                    )

                self.selector.mark_cooldown(
                    selected_key.key,
                    cooldown_info.hours,
                    cooldown_info.reason,
                )
                self.selector.update_last_failed_key(selected_key.key)
                self._sync_and_save()
                logger.info(
                    "key_cooldown key_id=%s reason=%s hours=%d attempt=%d/%d",
                    get_key_id(selected_key.key),
                    cooldown_info.reason,
                    cooldown_info.hours,
                    attempt + 1,
                    MAX_RETRIES,
                )
                if attempt < MAX_RETRIES - 1:
                    continue

                self._record_request(
                    request_id=request_id,
                    method=method,
                    path=path,
                    status_code=response.status_code,
                    key_id=get_key_id(selected_key.key),
                    latency=latency,
                )
                return RetryResult(
                    response=response,
                    success=False,
                    attempts=attempt + 1,
                    last_error="Rate limited",
                )

            # Success
            self.selector.update_last_failed_key(None)
            self.selector.last_used_key = selected_key.key
            logger.info(
                "request_done path=%s status=%d key_id=%s",
                path,
                response.status_code,
                get_key_id(selected_key.key),
            )
            self._record_request(
                request_id=request_id,
                method=method,
                path=path,
                status_code=response.status_code,
                key_id=get_key_id(selected_key.key),
                latency=latency,
            )
            return RetryResult(
                response=response,
                success=True,
                attempts=attempt + 1,
            )

        return RetryResult(
            response=None,
            success=False,
            attempts=MAX_RETRIES,
            last_error="Max retries exceeded",
        )

    async def prepare_stream_with_retry(
        self,
        method: str,
        path: str,
        headers: dict,
        body: dict | None,
        proxy: "ProxyClient",
        request_id: str,
    ) -> StreamSetupResult:
        """Prepare an upstream stream, retrying only before downstream bytes begin."""
        for attempt in range(MAX_RETRIES):
            selected_key = self.selector.acquire_stream_lease()
            if selected_key is None:
                logger.warning("all_stream_keys_exhausted path=%s", path)
                return StreamSetupResult(
                    success=False,
                    attempts=attempt,
                    last_error="No available API keys",
                )

            headers["Authorization"] = f"Bearer {selected_key.key}"
            start_ts = time.perf_counter()
            stream_context = proxy.forward_stream(
                method=method,
                path=path,
                headers=headers,
                json_data=body,
            )

            try:
                response = await stream_context.__aenter__()
                latency = round((time.perf_counter() - start_ts) * 1000, 2)
                cooldown_info = self.handler.detect_cooldown(response)

                if cooldown_info:
                    if cooldown_info.action == KeyAction.DISABLE:
                        self.selector.mark_disabled(
                            selected_key.key,
                            cooldown_info.reason,
                        )
                        self.selector.update_last_failed_key(selected_key.key)
                        self._sync_and_save()
                        logger.warning(
                            "stream_key_disabled key_id=%s reason=%s attempt=%d/%d",
                            get_key_id(selected_key.key),
                            cooldown_info.reason,
                            attempt + 1,
                            MAX_RETRIES,
                        )
                        error_text = f"Key disabled: {cooldown_info.reason}"
                    else:
                        self.selector.mark_cooldown(
                            selected_key.key,
                            cooldown_info.hours,
                            cooldown_info.reason,
                        )
                        self.selector.update_last_failed_key(selected_key.key)
                        self._sync_and_save()
                        logger.info(
                            "stream_key_cooldown key_id=%s reason=%s hours=%d attempt=%d/%d",
                            get_key_id(selected_key.key),
                            cooldown_info.reason,
                            cooldown_info.hours,
                            attempt + 1,
                            MAX_RETRIES,
                        )
                        error_text = "Rate limited"

                    error_body = await response.aread()
                    await stream_context.__aexit__(None, None, None)
                    self.selector.release_stream_lease(selected_key.key)

                    if attempt < MAX_RETRIES - 1:
                        continue

                    self._record_request(
                        request_id=request_id,
                        method=method,
                        path=path,
                        status_code=response.status_code,
                        key_id=get_key_id(selected_key.key),
                        latency=latency,
                    )
                    return StreamSetupResult(
                        success=False,
                        attempts=attempt + 1,
                        error_status_code=response.status_code,
                        error_body=error_body,
                        error_headers=dict(response.headers),
                        last_error=error_text,
                    )

                if response.status_code >= 400:
                    error_body = await response.aread()
                    await stream_context.__aexit__(None, None, None)
                    self.selector.release_stream_lease(selected_key.key)
                    self._record_request(
                        request_id=request_id,
                        method=method,
                        path=path,
                        status_code=response.status_code,
                        key_id=get_key_id(selected_key.key),
                        latency=latency,
                    )
                    return StreamSetupResult(
                        success=False,
                        attempts=attempt + 1,
                        error_status_code=response.status_code,
                        error_body=error_body,
                        error_headers=dict(response.headers),
                    )

                chunk_iterator = response.aiter_bytes()
                first_chunk = await anext(chunk_iterator, None)
                self.selector.update_last_failed_key(None)
                self.selector.last_used_key = selected_key.key
                logger.info(
                    "stream_request_ready path=%s status=%d key_id=%s",
                    path,
                    response.status_code,
                    get_key_id(selected_key.key),
                )
                return StreamSetupResult(
                    success=True,
                    attempts=attempt + 1,
                    response=response,
                    stream_context=stream_context,
                    selected_key=selected_key,
                    first_chunk=first_chunk,
                    chunk_iterator=chunk_iterator,
                )
            except Exception as e:
                latency = round((time.perf_counter() - start_ts) * 1000, 2)
                self.selector.release_stream_lease(selected_key.key)
                try:
                    await stream_context.__aexit__(type(e), e, e.__traceback__)
                except Exception:
                    pass
                logger.error(
                    "stream_proxy_error key_id=%s path=%s attempt=%d/%d error_type=%s error=%r latency=%.2fms",
                    get_key_id(selected_key.key),
                    path,
                    attempt + 1,
                    MAX_RETRIES,
                    type(e).__name__,
                    e,
                    latency,
                )
                if attempt < MAX_RETRIES - 1:
                    continue
                self._record_request(
                    request_id=request_id,
                    method=method,
                    path=path,
                    status_code=502,
                    key_id=get_key_id(selected_key.key),
                    latency=latency,
                )
                return StreamSetupResult(
                    success=False,
                    attempts=attempt + 1,
                    last_error=str(e),
                )

        return StreamSetupResult(
            success=False,
            attempts=MAX_RETRIES,
            last_error="Max retries exceeded",
        )

    def _record_request(
        self,
        request_id: str,
        method: str,
        path: str,
        status_code: int,
        key_id: str | None,
        latency: float,
    ) -> None:
        """Record a request to history."""
        record = RequestRecord(
            timestamp=datetime.now(timezone.utc),
            request_id=request_id,
            method=method,
            path=path,
            status_code=status_code,
            key_id=key_id,
            latency_ms=latency,
        )
        self.history.add(record)

    def record_stream_completion(
        self,
        request_id: str,
        method: str,
        path: str,
        status_code: int,
        key_id: str | None,
        latency: float,
    ) -> None:
        """Record the final outcome of a streaming request."""
        self._record_request(
            request_id=request_id,
            method=method,
            path=path,
            status_code=status_code,
            key_id=key_id,
            latency=latency,
        )
