from __future__ import annotations

import asyncio
import time
from typing import Any, Optional

import httpx

from .config import SentinelConfig, get_config
from .exceptions import ApprovalTimeout, SentinelAPIError, SentinelConfigError, SentinelError

USER_AGENT = "sentinel-sdk-python/0.1.4"


def _raise_for_status(r: httpx.Response) -> None:
    """Translate non-2xx into SentinelAPIError with the API's error body."""
    if r.is_success:
        return
    detail = ""
    try:
        body = r.json()
        if isinstance(body, dict):
            detail = body.get("detail") or body.get("message") or str(body)
        else:
            detail = str(body)
    except Exception:
        detail = (r.text or "")[:500]
    raise SentinelAPIError(r.status_code, detail, url=str(r.request.url))


class SentinelClient:
    """Thread-safe Sentinel client with HTTP connection keep-alive.

    A single httpx.Client is reused across calls — avoids ~95 ms TLS handshake
    on every request, which compounds when polling.
    """

    def __init__(self, config: Optional[SentinelConfig] = None):
        self.config = config or get_config()
        self._client: Optional[httpx.Client] = None
        self._aclient: Optional[httpx.AsyncClient] = None

    # ------------- internals -------------
    def _headers(self) -> dict:
        if not self.config.api_key:
            raise SentinelConfigError("Call sentinel.configure(api_key=...) before using Sentinel")
        return {
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}",
        }

    def _url(self, path: str) -> str:
        return f"{self.config.api_url.rstrip('/')}{path}"

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.config.api_url.rstrip("/"),
                headers=self._headers(),
                timeout=60.0,
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
            )
        return self._client

    def _get_aclient(self) -> httpx.AsyncClient:
        if self._aclient is None:
            self._aclient = httpx.AsyncClient(
                base_url=self.config.api_url.rstrip("/"),
                headers=self._headers(),
                timeout=60.0,
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
            )
        return self._aclient

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    async def aclose(self) -> None:
        if self._aclient is not None:
            await self._aclient.aclose()
            self._aclient = None

    # ------------- sync API -------------
    def create_approval(
        self,
        function_name: str,
        arguments: Any,
        risk_level: str = "medium",
        approvers: Optional[list] = None,
        timeout_seconds: Optional[float] = None,
    ) -> dict:
        payload = {
            "function_name": function_name,
            "arguments": arguments,
            "risk_level": risk_level,
            "approvers": approvers or [],
            "timeout_seconds": timeout_seconds or self.config.timeout_seconds,
        }
        r = self._get_client().post("/v1/approvals", json=payload)
        _raise_for_status(r)
        return r.json()

    def get_approval(self, action_id: str) -> dict:
        r = self._get_client().get(f"/v1/approvals/{action_id}")
        _raise_for_status(r)
        return r.json()

    def wait_for_decision(
        self,
        action_id: str,
        timeout: Optional[float] = None,
        poll_interval: Optional[float] = None,
    ) -> dict:
        """Block until the approval is decided or the timeout elapses.

        Uses the server-side long-poll endpoint when available (single RTT per
        ~30s wait window), falling back to client polling.
        """
        timeout = timeout or self.config.timeout_seconds
        deadline = time.monotonic() + timeout
        while True:
            remaining = max(1.0, min(30.0, deadline - time.monotonic()))
            try:
                r = self._get_client().get(
                    f"/v1/approvals/{action_id}/wait",
                    params={"timeout": remaining},
                    timeout=remaining + 5.0,
                )
                _raise_for_status(r)
                data = r.json()
            except SentinelAPIError as e:
                # Fall back to plain polling if /wait isn't available (older server)
                if e.status_code != 404:
                    raise
                data = self.get_approval(action_id)
            status = data.get("status") or data.get("decision")
            if status in ("approved", "rejected"):
                return data
            if time.monotonic() >= deadline:
                raise ApprovalTimeout(action_id=action_id, timeout_seconds=timeout)

    def list_audit_events(self, action_id: Optional[str] = None) -> list:
        params = {"action_id": action_id} if action_id else None
        r = self._get_client().get("/v1/audit-events", params=params)
        _raise_for_status(r)
        return r.json()

    def emit_audit_event(
        self,
        action_id: str,
        execution_result: Any = None,
        error: Optional[str] = None,
    ) -> None:
        payload = {
            "action_id": action_id,
            "execution_result": execution_result,
            "error": error,
        }
        try:
            self._get_client().post("/v1/audit-events", json=payload, timeout=10.0)
        except Exception:
            # best-effort — never raises
            pass

    # ------------- async API -------------
    async def acreate_approval(
        self,
        function_name: str,
        arguments: Any,
        risk_level: str = "medium",
        approvers: Optional[list] = None,
        timeout_seconds: Optional[float] = None,
    ) -> dict:
        payload = {
            "function_name": function_name,
            "arguments": arguments,
            "risk_level": risk_level,
            "approvers": approvers or [],
            "timeout_seconds": timeout_seconds or self.config.timeout_seconds,
        }
        r = await self._get_aclient().post("/v1/approvals", json=payload)
        _raise_for_status(r)
        return r.json()

    async def aget_approval(self, action_id: str) -> dict:
        r = await self._get_aclient().get(f"/v1/approvals/{action_id}")
        _raise_for_status(r)
        return r.json()

    async def await_for_decision(
        self,
        action_id: str,
        timeout: Optional[float] = None,
        poll_interval: Optional[float] = None,
    ) -> dict:
        timeout = timeout or self.config.timeout_seconds
        deadline = time.monotonic() + timeout
        while True:
            remaining = max(1.0, min(30.0, deadline - time.monotonic()))
            try:
                r = await self._get_aclient().get(
                    f"/v1/approvals/{action_id}/wait",
                    params={"timeout": remaining},
                    timeout=remaining + 5.0,
                )
                _raise_for_status(r)
                data = r.json()
            except SentinelAPIError as e:
                if e.status_code != 404:
                    raise
                data = await self.aget_approval(action_id)
            status = data.get("status") or data.get("decision")
            if status in ("approved", "rejected"):
                return data
            if time.monotonic() >= deadline:
                raise ApprovalTimeout(action_id=action_id, timeout_seconds=timeout)

    async def alist_audit_events(self, action_id: Optional[str] = None) -> list:
        params = {"action_id": action_id} if action_id else None
        r = await self._get_aclient().get("/v1/audit-events", params=params)
        _raise_for_status(r)
        return r.json()

    async def aemit_audit_event(
        self,
        action_id: str,
        execution_result: Any = None,
        error: Optional[str] = None,
    ) -> None:
        payload = {
            "action_id": action_id,
            "execution_result": execution_result,
            "error": error,
        }
        try:
            await self._get_aclient().post("/v1/audit-events", json=payload, timeout=10.0)
        except Exception:
            pass


__all__ = ["SentinelClient", "SentinelError", "SentinelAPIError"]
