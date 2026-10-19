"""Exception audits must be a body the API will store.

POST /v1/audit-events types execution_result as a required string. JSON null
is a 422. emit_audit_event / aemit_audit_event swallow delivery failures, so
a rejected body is a lost audit. An approved wrapped function that raises
used to send execution_result=null.
"""

import json

import httpx
import pytest

from sentinel import SentinelClient, oversight
from sentinel.config import SentinelConfig


def _cfg() -> SentinelConfig:
    return SentinelConfig(api_key="sk_test", api_url="https://api.test", timeout_seconds=5)


def _read_json(request: httpx.Request) -> dict:
    return json.loads(request.content.decode())


def _client_with_transport(captured: list, handler) -> SentinelClient:
    client = SentinelClient(_cfg())
    transport = httpx.MockTransport(handler)
    client._client = httpx.Client(
        base_url="https://api.test",
        headers=client._headers(),
        transport=transport,
    )
    client._aclient = httpx.AsyncClient(
        base_url="https://api.test",
        headers=client._headers(),
        transport=transport,
    )
    return client


def test_emit_audit_event_replaces_null_result_when_error_is_set():
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"id": "evt_1"})

    client = _client_with_transport(captured, handler)
    client.emit_audit_event("act_1", execution_result=None, error="ValueError('nope')")

    assert len(captured) == 1
    body = _read_json(captured[0])
    assert captured[0].url.path == "/v1/audit-events"
    assert body["action_id"] == "act_1"
    assert body["execution_result"] == "failed"
    assert isinstance(body["execution_result"], str)
    assert body["error"] == "ValueError('nope')"


def test_emit_audit_event_keeps_string_result():
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"id": "evt_1"})

    client = _client_with_transport(captured, handler)
    client.emit_audit_event("act_1", execution_result="'ok'", error="timeout-fallback-execute")

    body = _read_json(captured[0])
    assert body["execution_result"] == "'ok'"
    assert body["error"] == "timeout-fallback-execute"


def test_emit_audit_event_empty_string_when_both_missing():
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"id": "evt_1"})

    client = _client_with_transport(captured, handler)
    client.emit_audit_event("act_1")

    body = _read_json(captured[0])
    assert body["execution_result"] == ""
    assert isinstance(body["execution_result"], str)
    assert body["error"] is None


@pytest.mark.asyncio
async def test_aemit_audit_event_replaces_null_result():
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"id": "evt_1"})

    client = _client_with_transport(captured, handler)
    await client.aemit_audit_event("act_1", execution_result=None, error="RuntimeError('x')")

    body = _read_json(captured[0])
    assert body["execution_result"] == "failed"
    assert body["error"] == "RuntimeError('x')"


def _patch_decorator_client(monkeypatch, captured: list):
    cfg = _cfg()

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        path = request.url.path
        if request.method == "POST" and path == "/v1/approvals":
            return httpx.Response(200, json={"action_id": "act_exc", "status": "pending"})
        if path.endswith("/wait"):
            return httpx.Response(200, json={"action_id": "act_exc", "status": "approved"})
        if request.method == "POST" and path == "/v1/audit-events":
            return httpx.Response(200, json={"id": "evt_1"})
        return httpx.Response(500, json={"detail": f"unexpected {request.method} {path}"})

    def factory(config=None):
        return _client_with_transport(captured, handler)

    monkeypatch.setattr("sentinel.decorator.get_config", lambda: cfg)
    monkeypatch.setattr("sentinel.decorator.SentinelClient", factory)


def _audit_posts(captured: list[httpx.Request]) -> list[dict]:
    return [
        _read_json(request)
        for request in captured
        if request.method == "POST" and request.url.path == "/v1/audit-events"
    ]


def test_approved_sync_exception_posts_string_execution_result(monkeypatch):
    captured: list[httpx.Request] = []
    _patch_decorator_client(monkeypatch, captured)
    calls = {"n": 0}

    @oversight(risk_level="high")
    def explode(amount):
        calls["n"] += 1
        raise ValueError("nope")

    with pytest.raises(ValueError, match="nope"):
        explode(3)

    assert calls["n"] == 1
    audits = _audit_posts(captured)
    assert len(audits) == 1
    assert audits[0]["action_id"] == "act_exc"
    assert audits[0]["execution_result"] == "failed"
    assert "ValueError" in audits[0]["error"]
    assert "nope" in audits[0]["error"]


@pytest.mark.asyncio
async def test_approved_async_exception_posts_string_execution_result(monkeypatch):
    captured: list[httpx.Request] = []
    _patch_decorator_client(monkeypatch, captured)
    calls = {"n": 0}

    @oversight()
    async def explode(amount):
        calls["n"] += 1
        raise RuntimeError("async nope")

    with pytest.raises(RuntimeError, match="async nope"):
        await explode(3)

    assert calls["n"] == 1
    audits = _audit_posts(captured)
    assert len(audits) == 1
    assert audits[0]["execution_result"] == "failed"
    assert "RuntimeError" in audits[0]["error"]
    assert "async nope" in audits[0]["error"]


def test_approved_sync_success_result_unchanged(monkeypatch):
    captured: list[httpx.Request] = []
    _patch_decorator_client(monkeypatch, captured)

    @oversight()
    def ok(amount):
        return {"amount": amount}

    assert ok(3) == {"amount": 3}
    audits = _audit_posts(captured)
    assert len(audits) == 1
    assert audits[0]["execution_result"] == "{'amount': 3}"
    assert audits[0]["error"] is None
