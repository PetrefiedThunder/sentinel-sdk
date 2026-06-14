"""Idempotency-Key support on POST /v1/approvals (client + decorator)."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from sentinel import SentinelClient, oversight
from sentinel.config import SentinelConfig

_APPROVAL_BODY = {"action_id": "act_1", "status": "pending"}


def _make_client(captured: list) -> SentinelClient:
    """Real SentinelClient with an httpx MockTransport that records requests.

    Uses the client's own default headers so the test verifies the real
    httpx merge behavior (per-request headers must not drop Authorization).
    """
    client = SentinelClient(SentinelConfig(api_key="sk_test", api_url="https://api.test"))

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=_APPROVAL_BODY)

    client._client = httpx.Client(
        base_url="https://api.test",
        headers=client._headers(),
        transport=httpx.MockTransport(handler),
    )
    client._aclient = httpx.AsyncClient(
        base_url="https://api.test",
        headers=client._headers(),
        transport=httpx.MockTransport(handler),
    )
    return client


# ------------- client: sync -------------
def test_header_sent_with_exact_value():
    captured = []
    client = _make_client(captured)
    client.create_approval(function_name="transfer", arguments={"a": 1}, idempotency_key="key-123")
    assert captured[0].headers["Idempotency-Key"] == "key-123"


def test_header_absent_when_not_set():
    captured = []
    client = _make_client(captured)
    client.create_approval(function_name="transfer", arguments={"a": 1})
    assert "Idempotency-Key" not in captured[0].headers


def test_header_merge_keeps_authorization():
    captured = []
    client = _make_client(captured)
    client.create_approval(function_name="transfer", arguments={"a": 1}, idempotency_key="key-123")
    assert captured[0].headers["Authorization"] == "Bearer sk_test"
    assert captured[0].headers["Idempotency-Key"] == "key-123"


# ------------- client: async -------------
@pytest.mark.asyncio
async def test_async_header_sent_with_exact_value():
    captured = []
    client = _make_client(captured)
    await client.acreate_approval(
        function_name="transfer", arguments={"a": 1}, idempotency_key="akey-456"
    )
    assert captured[0].headers["Idempotency-Key"] == "akey-456"
    assert captured[0].headers["Authorization"] == "Bearer sk_test"


@pytest.mark.asyncio
async def test_async_header_absent_when_not_set():
    captured = []
    client = _make_client(captured)
    await client.acreate_approval(function_name="transfer", arguments={"a": 1})
    assert "Idempotency-Key" not in captured[0].headers


# ------------- decorator: sync -------------
@patch("sentinel.decorator.SentinelClient")
def test_decorator_string_key_passed_through(mock_client_cls):
    mock_client = MagicMock()
    mock_client.create_approval.return_value = {"action_id": "act_1"}
    mock_client.wait_for_decision.return_value = {"status": "approved"}
    mock_client_cls.return_value = mock_client

    @oversight(idempotency_key="fixed-key")
    def task():
        return "ok"

    assert task() == "ok"
    assert task() == "ok"
    for call in mock_client.create_approval.call_args_list:
        assert call.kwargs["idempotency_key"] == "fixed-key"


@patch("sentinel.decorator.SentinelClient")
def test_decorator_callable_invoked_per_call(mock_client_cls):
    mock_client = MagicMock()
    mock_client.create_approval.return_value = {"action_id": "act_1"}
    mock_client.wait_for_decision.return_value = {"status": "approved"}
    mock_client_cls.return_value = mock_client

    counter = {"n": 0}

    def keygen():
        counter["n"] += 1
        return f"key-{counter['n']}"

    @oversight(idempotency_key=keygen)
    def task():
        return "ok"

    task()
    task()
    keys = [c.kwargs["idempotency_key"] for c in mock_client.create_approval.call_args_list]
    assert keys == ["key-1", "key-2"]
    assert counter["n"] == 2


@patch("sentinel.decorator.SentinelClient")
def test_decorator_none_key_not_passed(mock_client_cls):
    mock_client = MagicMock()
    mock_client.create_approval.return_value = {"action_id": "act_1"}
    mock_client.wait_for_decision.return_value = {"status": "approved"}
    mock_client_cls.return_value = mock_client

    @oversight()
    def task():
        return "ok"

    task()
    assert "idempotency_key" not in mock_client.create_approval.call_args.kwargs


# ------------- decorator: async -------------
@pytest.mark.asyncio
@patch("sentinel.decorator.SentinelClient")
async def test_decorator_async_callable_invoked_per_call(mock_client_cls):
    mock_client = MagicMock()
    mock_client.acreate_approval = AsyncMock(return_value={"action_id": "act_1"})
    mock_client.await_for_decision = AsyncMock(return_value={"status": "approved"})
    mock_client.aemit_audit_event = AsyncMock()
    mock_client_cls.return_value = mock_client

    counter = {"n": 0}

    def keygen():
        counter["n"] += 1
        return f"akey-{counter['n']}"

    @oversight(idempotency_key=keygen)
    async def task():
        return "ok"

    assert await task() == "ok"
    assert await task() == "ok"
    keys = [c.kwargs["idempotency_key"] for c in mock_client.acreate_approval.call_args_list]
    assert keys == ["akey-1", "akey-2"]
