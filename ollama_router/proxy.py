import logging
from typing import Any

import httpx

logger = logging.getLogger("ollama_router")

# Claude Code coding tasks can take a very long time (complex refactors, etc.)
# 1800s = 30 minutes per request to match typical Claude Code usage patterns.
UPSTREAM_TIMEOUT = 1800.0


class ProxyClient:
    def __init__(
        self,
        upstream: str,
        proxy_http: str | None = None,
        proxy_https: str | None = None,
    ):
        self.upstream = upstream.rstrip("/")

        # Use an explicit proxy transport when a proxy URL is provided in config.
        # When no proxy is configured here, do NOT create a custom transport —
        # httpx will create its own default transport with trust_env=True, which
        # correctly reads HTTPS_PROXY / https_proxy from the environment.
        # (Providing a custom transport bypasses trust_env proxy routing.)
        proxy_url = proxy_https or proxy_http
        if proxy_url:
            logger.info("proxy_configured url=%s", proxy_url)
            transport = httpx.AsyncHTTPTransport(proxy=proxy_url)
            self.client = httpx.AsyncClient(
                timeout=httpx.Timeout(UPSTREAM_TIMEOUT, connect=30.0),
                transport=transport,
            )
        else:
            self.client = httpx.AsyncClient(
                timeout=httpx.Timeout(UPSTREAM_TIMEOUT, connect=30.0),
            )

    async def forward(
        self,
        method: str,
        path: str,
        headers: dict[str, str],
        json_data: dict[str, Any] | None = None,
    ) -> httpx.Response:
        effective_path = path.lstrip("/")
        if effective_path.startswith("v1/"):
            effective_path = effective_path[3:]
            upstream = self.upstream.rstrip("/v1")
            url = f"{upstream}/v1/{effective_path}"
        else:
            url = f"{self.upstream}/{effective_path}"

        new_headers = {"Authorization": headers.get("Authorization", "")}

        return await self.client.request(
            method=method,
            url=url,
            headers=new_headers,
            json=json_data,
        )

    async def close(self):
        await self.client.aclose()
