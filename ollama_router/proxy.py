import os
from typing import Any

import httpx


class ProxyClient:
    def __init__(
        self,
        upstream: str,
        proxy_http: str | None = None,
        proxy_https: str | None = None,
    ):
        self.upstream = upstream.rstrip("/")
        self.client = httpx.AsyncClient(
            timeout=60.0,
            trust_env=True,
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
