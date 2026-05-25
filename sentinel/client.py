from __future__ import annotations

import asyncio
import time
from typing import Any, Optional

import httpx

from .config import SentinelConfig, get_config
from .exceptions import ApprovalTimeout, SentinelAPIError, SentinelConfigError, SentinelError

USER_AGENT = "sentinel-sdk-python/0.1.2"


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
    def __init__(self, config: Optional[SentinelConfig] = None):
        self.config = config or get_config()

    # ------------- internals -------------
    def _headers(self) -> dict:
        if not self.config.api_key:
            raise SentinelConfigError("Call sentinel.configure(api_key=...) before using Sentinel")
        h = {"User-Agent": USER_AGENT, "Content-Type": "application/json"}
        h["Authorization"] = f"Bearer {self.config.api_key}"
        return h

    def _url(self, path: str) -> str:
        return f"{self.config.api_url.rstrip('/')}{path}"

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
        with httpx.Client(timeout=30.0) as c:
            r = c.post(self._url("/v1/approvals"), json=payload, headers=self._headers())
            _raise_for_status(r)
            return r.json()

    def get_approval(self, action_id: str) -> dict:
        with httpx.Client(timeout=30.0) as c:
            r = c.get(self._url(f"/v1/approvals/{action_id}"), headers=self._headers())
            _raise_for_status(r)
            return r.json()

    def wait_for_decision(
        self,
        action_id: str,
        timeout: Optional[float] = None,
        poll_interval: Optional[float] = None,
    ) -> dict:
        timeout = timeout or self.config.timeout_seconds
        poll_interval = poll_interval or self.config.poll_interval
        deadline = time.monotonic() + timeout
        while True:
            data = self.get_approval(action_id)
            status = data.get("status") or data.get("decision")
            if status in ("approved", "rejected"):
                return data
            if time.monotonic() >= deadline:
                raise ApprovalTimeout(action_id=action_id, timeout_seconds=timeout)
            time.sleep(poll_interval)

    def list_audit_events(self, action_id: Optional[str] = None) -> list:
        params = {"action_id": action_id} if action_id else None
        with httpx.Client(timeout=30.0) as c:
            r = c.get(self._url("/v1/audit-events"), params=params, headers=self._headers())
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
            with httpx.Client(timeout=10.0) as c:
                c.post(self._url("/v1/audit-events"), json=payload, headers=self._headers())
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
        async with httpx.AsyncClient(timeout=30.0) as c:
            r = await c.post(self._url("/v1/approvals"), json=payload, headers=self._headers())
            _raise_for_status(r)
            return r.json()

    async def aget_approval(self, action_id: str) -> dict:
        async with httpx.AsyncClient(timeout=30.0) as c:
            r = await c.get(self._url(f"/v1/approvals/{action_id}"), headers=self._headers())
            _raise_for_status(r)
            return r.json()

    async def await_for_decision(
        self,
        action_id: str,
        timeout: Optional[float] = None,
        poll_interval: Optional[float] = None,
    ) -> dict:
        timeout = timeout or self.config.timeout_seconds
        poll_interval = poll_interval or self.config.poll_interval
        deadline = time.monotonic() + timeout
        while True:
            data = await self.aget_approval(action_id)
            status = data.get("status") or data.get("decision")
            if status in ("approved", "rejected"):
                return data
            if time.monotonic() >= deadline:
                raise ApprovalTimeout(action_id=action_id, timeout_seconds=timeout)
            await asyncio.sleep(poll_interval)

    async def alist_audit_events(self, action_id: Optional[str] = None) -> list:
        params = {"action_id": action_id} if action_id else None
        async with httpx.AsyncClient(timeout=30.0) as c:
            r = await c.get(self._url("/v1/audit-events"), params=params, headers=self._headers())
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
            async with httpx.AsyncClient(timeout=10.0) as c:
                await c.post(self._url("/v1/audit-events"), json=payload, headers=self._headers())
        except Exception:
            pass


__all__ = ["SentinelClient", "SentinelError", "SentinelAPIError"]
