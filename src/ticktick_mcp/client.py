from __future__ import annotations

import json
import logging
import time
from typing import Any
from urllib.parse import quote

import httpx

from ticktick_mcp.auth import refresh_access_token

logger = logging.getLogger(__name__)

V1_BASE = "https://api.ticktick.com/open/v1"
V2_BASE = "https://api.ticktick.com/api/v2"
V3_BASE = "https://api.ticktick.com/api/v3"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)


def generate_device_id() -> str:
    """Fabricate a device ID shaped like the TickTick web client's.

    The v2 API's ``x-device`` header must carry an ID in the web client's
    "6490" + 20-hex-digit form, or the server treats the session as untrusted.
    The value only has to look plausible and stay stable for the session, so a
    cheap LCG seeded on the clock is sufficient — no cryptographic randomness
    is warranted here.
    """
    state = time.time_ns()
    hex_digits: list[str] = []
    for _ in range(20):
        state = (state * 6364136223846793005 + 1442695040888963407) & 0xFFFFFFFFFFFFFFFF
        # Sample a middle bit range; the low bits of an LCG are notoriously non-random.
        hex_digits.append(f"{(state >> 33) & 0xF:x}")
    return "6490" + "".join(hex_digits)


def x_device_header(device_id: str) -> str:
    """Serialize the ``x-device`` header the v2 API uses to identify the client."""
    return json.dumps(
        {
            "platform": "web",
            "os": "macOS 10.15.7",
            "device": "Chrome 130.0.0.0",
            "name": "",
            "version": 6490,
            "id": device_id,
            "channel": "website",
            "campaign": "",
            "websocket": "",
        },
        separators=(",", ":"),
    )


def url_encode(s: str) -> str:
    """Percent-encode a string for URL query parameters."""
    return quote(s, safe="")


class TickTickClient:
    """Async HTTP client for the TickTick API (v1, v2, v3, ms)."""

    def __init__(
        self,
        access_token: str,
        client_id: str | None = None,
        client_secret: str | None = None,
        session_token: str | None = None,
        refresh_token: str | None = None,
    ) -> None:
        self._access_token = access_token
        self._client_id = client_id
        self._client_secret = client_secret
        self._session_token = session_token
        self._refresh_token = refresh_token
        self._device_id = generate_device_id()
        self._http: httpx.AsyncClient | None = None
        self._inbox_project_id: str | None = None

    async def __aenter__(self) -> TickTickClient:
        self._http = httpx.AsyncClient(timeout=30.0)
        return self

    async def __aexit__(self, *args: object) -> None:
        if self._http:
            await self._http.aclose()
            self._http = None

    @property
    def http(self) -> httpx.AsyncClient:
        if self._http is None:
            raise RuntimeError("Client not initialized. Use 'async with client:' context manager.")
        return self._http

    # ------------------------------------------------------------------
    # v1 API — Bearer auth with auto-refresh on 401
    # ------------------------------------------------------------------

    def _v1_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._access_token}"}

    async def _try_refresh(self) -> bool:
        """Attempt to refresh the access token. Returns True on success."""
        if not (self._refresh_token and self._client_id and self._client_secret):
            return False
        try:
            new_access, new_refresh = await refresh_access_token(
                self.http, self._refresh_token, self._client_id, self._client_secret
            )
            self._access_token = new_access
            if new_refresh:
                self._refresh_token = new_refresh
            logger.info("Token refreshed automatically")
            return True
        except Exception:
            logger.warning("Token refresh failed")
            return False

    async def v1_get(self, endpoint: str) -> Any:
        resp = await self.http.get(f"{V1_BASE}{endpoint}", headers=self._v1_headers())
        if resp.status_code == 401 and await self._try_refresh():
            resp = await self.http.get(f"{V1_BASE}{endpoint}", headers=self._v1_headers())
        resp.raise_for_status()
        return resp.json()

    async def v1_post(self, endpoint: str, json_data: Any = None) -> Any:
        resp = await self.http.post(
            f"{V1_BASE}{endpoint}", headers=self._v1_headers(), json=json_data
        )
        if resp.status_code == 401 and await self._try_refresh():
            resp = await self.http.post(
                f"{V1_BASE}{endpoint}", headers=self._v1_headers(), json=json_data
            )
        resp.raise_for_status()
        return resp.json() if resp.content else None

    async def v1_post_empty(self, endpoint: str) -> httpx.Response:
        resp = await self.http.post(f"{V1_BASE}{endpoint}", headers=self._v1_headers())
        if resp.status_code == 401 and await self._try_refresh():
            resp = await self.http.post(f"{V1_BASE}{endpoint}", headers=self._v1_headers())
        resp.raise_for_status()
        return resp

    async def v1_delete(self, endpoint: str) -> httpx.Response:
        resp = await self.http.delete(f"{V1_BASE}{endpoint}", headers=self._v1_headers())
        if resp.status_code == 401 and await self._try_refresh():
            resp = await self.http.delete(f"{V1_BASE}{endpoint}", headers=self._v1_headers())
        resp.raise_for_status()
        return resp

    # ------------------------------------------------------------------
    # v2 API — Cookie auth with x-device header
    # ------------------------------------------------------------------

    def _require_session(self) -> str:
        if not self._session_token:
            raise RuntimeError(
                "v2 session token not set. "
                "Set TICKTICK_V2_SESSION_TOKEN from the 't' cookie in your browser."
            )
        return self._session_token

    @staticmethod
    def _check_v2_response(resp: httpx.Response) -> None:
        """Raise clear errors for common v2 API failures."""
        if resp.status_code == 401:
            raise RuntimeError(
                "V2 session token is invalid or expired. "
                "Update TICKTICK_V2_SESSION_TOKEN with a fresh 't' cookie from your browser."
            )
        if resp.status_code == 403:
            raise RuntimeError("This feature requires a TickTick Premium subscription.")
        resp.raise_for_status()

    def _v2_headers(self) -> dict[str, str]:
        token = self._require_session()
        return {
            "User-Agent": USER_AGENT,
            "x-device": x_device_header(self._device_id),
            "Cookie": f"t={token}",
        }

    async def v2_get(self, endpoint: str) -> Any:
        resp = await self.http.get(f"{V2_BASE}{endpoint}", headers=self._v2_headers())
        self._check_v2_response(resp)
        return resp.json()

    async def v2_post(self, endpoint: str, json_data: Any) -> Any:
        resp = await self.http.post(
            f"{V2_BASE}{endpoint}", headers=self._v2_headers(), json=json_data
        )
        self._check_v2_response(resp)
        return resp.json() if resp.content else None

    async def v2_put(self, endpoint: str, json_data: Any) -> Any:
        resp = await self.http.put(
            f"{V2_BASE}{endpoint}", headers=self._v2_headers(), json=json_data
        )
        self._check_v2_response(resp)
        return resp.json() if resp.content else None

    async def v2_delete(self, endpoint: str) -> httpx.Response:
        resp = await self.http.delete(f"{V2_BASE}{endpoint}", headers=self._v2_headers())
        self._check_v2_response(resp)
        return resp

    # ------------------------------------------------------------------
    # v3 / batch check
    # ------------------------------------------------------------------

    async def batch_check(self) -> dict[str, Any]:
        """Full account state sync via v2 GET /batch/check/0."""
        return await self.v2_get("/batch/check/0")
