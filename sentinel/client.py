from __future__ import annotations

import contextlib
import json
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from .config import SentinelConfig, get_config
from .exceptions import ApprovalTimeout, SentinelAPIError, SentinelConfigError, SentinelError

USER_AGENT = "sentinel-sdk-python/0.1.9"


@dataclass
class PageResult:
    """One page of results from a cursor-paginated list endpoint.

    Mirrors the JS SDK's PageResult: `data` is the list of items, `has_more`
    indicates whether another page exists, and `next_cursor` is the opaque
    cursor to pass back to fetch it (None when there are no more pages).
    """

    data: list = field(default_factory=list)
    has_more: bool = False
    next_cursor: str | None = None

    @classmethod
    def from_envelope(cls, body: Any) -> PageResult:
        """Build a PageResult from the API's {data, has_more, next_cursor} body.

        Tolerates a bare list (older servers that return an unwrapped array):
        the whole list becomes a single terminal page.
        """
        if isinstance(body, dict):
            return cls(
                data=body.get("data") or [],
                has_more=bool(body.get("has_more", False)),
                next_cursor=body.get("next_cursor"),
            )
        return cls(data=list(body or []), has_more=False, next_cursor=None)


def _ensure_json_serializable(arguments: Any) -> None:
    """Fail fast if `arguments` can't be JSON-encoded.

    Without this check the POST silently succeeds (httpx converts the value
    via its own serializer, or the server stores something useless), and
    the agent then hangs until `timeout_seconds` waiting on a decision it
    can never get. Raise immediately with the offending type so the caller
    sees the real error.
    """
    try:
        json.dumps(arguments)
    except TypeError as e:
        raise TypeError(
            f"@oversight arguments must be JSON-serializable. "
            f"Got an un-serializable value: {e}. "
            f"Convert sets/objects/bytes to plain dict/list/str/int/float/bool/None before the call."
        ) from e


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

    def __init__(self, config: SentinelConfig | None = None):
        self.config = config or get_config()
        self._client: httpx.Client | None = None
        self._aclient: httpx.AsyncClient | None = None

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
        approvers: list | None = None,
        timeout_seconds: int | None = None,
        idempotency_key: str | None = None,
    ) -> dict:
        _ensure_json_serializable(arguments)
        payload = {
            "function_name": function_name,
            "arguments": arguments,
            "risk_level": risk_level,
            "approvers": approvers or [],
            # The API types timeout_seconds as an integer and 422s on a
            # fractional value. Coerce here so float configs/callers still work
            # (fractional seconds are truncated toward zero, e.g. 1.9 -> 1).
            "timeout_seconds": int(timeout_seconds or self.config.timeout_seconds),
        }
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        r = self._get_client().post("/v1/approvals", json=payload, headers=headers)
        _raise_for_status(r)
        return r.json()

    def get_approval(self, action_id: str) -> dict:
        r = self._get_client().get(f"/v1/approvals/{action_id}")
        _raise_for_status(r)
        return r.json()

    def list_approvals(
        self,
        status: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> PageResult:
        """List approvals one page at a time (cursor pagination).

        Mirrors the JS SDK's `listApprovals`. Always sends `limit` (default 50,
        server max 100) so the API returns the {data, has_more, next_cursor}
        envelope. Pass the returned `next_cursor` back as `cursor` for the next
        page; iterate until `has_more` is False.
        """
        params: dict[str, Any] = {"limit": limit}
        if status is not None:
            params["status"] = status
        if cursor is not None:
            params["cursor"] = cursor
        r = self._get_client().get("/v1/approvals", params=params)
        _raise_for_status(r)
        return PageResult.from_envelope(r.json())

    def wait_for_decision(
        self,
        action_id: str,
        timeout: float | None = None,
        poll_interval: float | None = None,
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

    def get_tenant(self) -> dict:
        """Fetch the current tenant's settings (default_approvers, etc)."""
        r = self._get_client().get("/v1/tenants/me")
        _raise_for_status(r)
        return r.json()

    def set_default_approvers(self, approvers: list[str]) -> dict:
        """Set the tenant's default-approvers list. Used when `@oversight()`
        decorators don't specify their own `approvers=[...]`.

        Example:
            client.set_default_approvers(["sms:+15551234567", "ops@acme.com"])
        """
        r = self._get_client().patch("/v1/tenants/me", json={"default_approvers": approvers})
        _raise_for_status(r)
        return r.json()

    def register_sms_contact(
        self,
        phone_number: str,
        display_name: str,
        consent_source: str,
        consent_note: str = "",
        consent_attested: bool = True,
    ) -> dict:
        """Register a phone number for SMS approvals (TCPA-compliant opt-in).

        You must have a recorded business-relationship opt-in (signed form,
        captured web checkbox, etc). The `consent_source` and `consent_note`
        fields are stored as evidence; `consent_attested=True` is the API's
        affirmative attestation that the opt-in was collected lawfully.

        Without this call, any `approvers=["sms:+1..."]` will be rejected with
        a 400 "SMS approver requires active SMS consent contact".
        """
        payload = {
            "phone_number": phone_number,
            "display_name": display_name,
            "consent_attested": bool(consent_attested),
            "consent_source": consent_source,
            "consent_note": consent_note,
        }
        r = self._get_client().post("/v1/approver-contacts", json=payload)
        _raise_for_status(r)
        return r.json()

    def list_sms_contacts(self) -> list:
        r = self._get_client().get("/v1/approver-contacts")
        _raise_for_status(r)
        return r.json()

    def revoke_sms_contact(self, contact_id: str) -> dict:
        r = self._get_client().delete(f"/v1/approver-contacts/{contact_id}")
        _raise_for_status(r)
        return r.json()

    def list_audit_events(self, action_id: str | None = None) -> list:
        params = {"action_id": action_id} if action_id else None
        r = self._get_client().get("/v1/audit-events", params=params)
        _raise_for_status(r)
        return r.json()

    def list_audit_events_page(
        self,
        action_id: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> PageResult:
        """List audit events one page at a time (cursor pagination).

        Mirrors the JS SDK's `listAuditEventsPage`. Unlike the legacy
        `list_audit_events()`, this always sends `limit` (default 50, server
        max 500) so the API returns the {data, has_more, next_cursor} envelope.
        """
        params: dict[str, Any] = {"limit": limit}
        if action_id is not None:
            params["action_id"] = action_id
        if cursor is not None:
            params["cursor"] = cursor
        r = self._get_client().get("/v1/audit-events", params=params)
        _raise_for_status(r)
        return PageResult.from_envelope(r.json())

    def emit_audit_event(
        self,
        action_id: str,
        execution_result: Any = None,
        error: str | None = None,
    ) -> None:
        payload = {
            "action_id": action_id,
            "execution_result": execution_result,
            "error": error,
        }
        try:  # noqa: SIM105 - keep explicit comment documenting best-effort intent
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
        approvers: list | None = None,
        timeout_seconds: int | None = None,
        idempotency_key: str | None = None,
    ) -> dict:
        _ensure_json_serializable(arguments)
        payload = {
            "function_name": function_name,
            "arguments": arguments,
            "risk_level": risk_level,
            "approvers": approvers or [],
            # See create_approval: API requires an integer; coerce to avoid 422.
            "timeout_seconds": int(timeout_seconds or self.config.timeout_seconds),
        }
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        r = await self._get_aclient().post("/v1/approvals", json=payload, headers=headers)
        _raise_for_status(r)
        return r.json()

    async def aget_approval(self, action_id: str) -> dict:
        r = await self._get_aclient().get(f"/v1/approvals/{action_id}")
        _raise_for_status(r)
        return r.json()

    async def alist_approvals(
        self,
        status: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> PageResult:
        """Async counterpart of `list_approvals`."""
        params: dict[str, Any] = {"limit": limit}
        if status is not None:
            params["status"] = status
        if cursor is not None:
            params["cursor"] = cursor
        r = await self._get_aclient().get("/v1/approvals", params=params)
        _raise_for_status(r)
        return PageResult.from_envelope(r.json())

    async def await_for_decision(
        self,
        action_id: str,
        timeout: float | None = None,
        poll_interval: float | None = None,
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

    async def aget_tenant(self) -> dict:
        r = await self._get_aclient().get("/v1/tenants/me")
        _raise_for_status(r)
        return r.json()

    async def aset_default_approvers(self, approvers: list[str]) -> dict:
        r = await self._get_aclient().patch("/v1/tenants/me", json={"default_approvers": approvers})
        _raise_for_status(r)
        return r.json()

    async def aregister_sms_contact(
        self,
        phone_number: str,
        display_name: str,
        consent_source: str,
        consent_note: str = "",
        consent_attested: bool = True,
    ) -> dict:
        payload = {
            "phone_number": phone_number,
            "display_name": display_name,
            "consent_attested": bool(consent_attested),
            "consent_source": consent_source,
            "consent_note": consent_note,
        }
        r = await self._get_aclient().post("/v1/approver-contacts", json=payload)
        _raise_for_status(r)
        return r.json()

    async def alist_sms_contacts(self) -> list:
        r = await self._get_aclient().get("/v1/approver-contacts")
        _raise_for_status(r)
        return r.json()

    async def arevoke_sms_contact(self, contact_id: str) -> dict:
        r = await self._get_aclient().delete(f"/v1/approver-contacts/{contact_id}")
        _raise_for_status(r)
        return r.json()

    async def alist_audit_events(self, action_id: str | None = None) -> list:
        params = {"action_id": action_id} if action_id else None
        r = await self._get_aclient().get("/v1/audit-events", params=params)
        _raise_for_status(r)
        return r.json()

    async def alist_audit_events_page(
        self,
        action_id: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> PageResult:
        """Async counterpart of `list_audit_events_page`."""
        params: dict[str, Any] = {"limit": limit}
        if action_id is not None:
            params["action_id"] = action_id
        if cursor is not None:
            params["cursor"] = cursor
        r = await self._get_aclient().get("/v1/audit-events", params=params)
        _raise_for_status(r)
        return PageResult.from_envelope(r.json())

    async def aemit_audit_event(
        self,
        action_id: str,
        execution_result: Any = None,
        error: str | None = None,
    ) -> None:
        payload = {
            "action_id": action_id,
            "execution_result": execution_result,
            "error": error,
        }
        with contextlib.suppress(Exception):
            await self._get_aclient().post("/v1/audit-events", json=payload, timeout=10.0)


__all__ = ["SentinelClient", "SentinelError", "SentinelAPIError", "PageResult"]
