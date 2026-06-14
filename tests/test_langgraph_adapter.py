import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from sentinel.adapters.langgraph import SentinelToolGate
from sentinel.exceptions import ApprovalRejected


def _approved_client():
    client = MagicMock()
    client.create_approval.return_value = {"action_id": "act_1"}
    client.wait_for_decision.return_value = {"status": "approved"}
    return client


def test_approved_runs_and_returns():
    client = _approved_client()
    gate = SentinelToolGate(client=client, risk_level="high")

    def search_web(query, limit=5):
        return {"query": query, "limit": limit}

    wrapped = gate.wrap(search_web)
    result = wrapped(query="cats", limit=3)

    assert result == {"query": "cats", "limit": 3}
    client.create_approval.assert_called_once_with(
        function_name="search_web",
        arguments={"query": "cats", "limit": 3},
        risk_level="high",
        approvers=None,
        timeout_seconds=None,
    )
    client.wait_for_decision.assert_called_once_with("act_1", timeout=None)


def test_positional_args_use_args_convention():
    client = _approved_client()
    gate = SentinelToolGate(client=client)

    def tool_fn(a, b):
        return a + b

    assert gate.wrap(tool_fn)(1, 2) == 3
    arguments = client.create_approval.call_args.kwargs["arguments"]
    assert arguments == {"args": [1, 2]}


def test_rejected_raises_and_fn_not_called():
    client = MagicMock()
    client.create_approval.return_value = {"action_id": "act_2"}
    client.wait_for_decision.return_value = {
        "status": "rejected",
        "reason": "too risky",
    }
    gate = SentinelToolGate(client=client)

    ran = {"v": False}

    def dangerous():
        ran["v"] = True
        return "done"

    with pytest.raises(ApprovalRejected) as exc:
        gate.wrap(dangerous)()
    assert "too risky" in str(exc.value)
    assert exc.value.action_id == "act_2"
    assert ran["v"] is False


def test_allowlist_unlisted_tool_calls_through():
    client = _approved_client()
    gate = SentinelToolGate(client=client, tool_allowlist=["wire_transfer"])

    def harmless():
        return "ok"

    assert gate.wrap(harmless)() == "ok"
    client.create_approval.assert_not_called()
    client.wait_for_decision.assert_not_called()


def test_allowlist_listed_tool_is_gated():
    client = _approved_client()
    gate = SentinelToolGate(client=client, tool_allowlist=["wire_transfer"])

    def wire_transfer():
        return "sent"

    assert gate.wrap(wire_transfer)() == "sent"
    client.create_approval.assert_called_once()


def test_denylist_listed_tool_skips_approval():
    client = _approved_client()
    gate = SentinelToolGate(client=client, tool_denylist=["read_only_lookup"])

    def read_only_lookup():
        return "data"

    assert gate.wrap(read_only_lookup)() == "data"
    client.create_approval.assert_not_called()


def test_explicit_function_name_overrides_fn_name():
    client = _approved_client()
    gate = SentinelToolGate(client=client)

    def fn():
        return "ok"

    gate.wrap(fn, function_name="custom_name")()
    assert client.create_approval.call_args.kwargs["function_name"] == "custom_name"


def test_async_fn_wrapped_is_awaitable():
    client = MagicMock()
    client.acreate_approval = AsyncMock(return_value={"action_id": "act_3"})
    client.await_for_decision = AsyncMock(return_value={"status": "approved"})
    gate = SentinelToolGate(client=client)

    async def async_tool(x):
        return x * 2

    wrapped = gate.wrap(async_tool)
    assert asyncio.iscoroutinefunction(wrapped)
    result = asyncio.run(wrapped(x=21))

    assert result == 42
    client.acreate_approval.assert_awaited_once_with(
        function_name="async_tool",
        arguments={"x": 21},
        risk_level="high",
        approvers=None,
        timeout_seconds=None,
    )
    client.await_for_decision.assert_awaited_once_with("act_3", timeout=None)


def test_async_rejected_raises():
    client = MagicMock()
    client.acreate_approval = AsyncMock(return_value={"action_id": "act_4"})
    client.await_for_decision = AsyncMock(return_value={"status": "rejected", "reason": "nope"})
    gate = SentinelToolGate(client=client)

    ran = {"v": False}

    async def async_dangerous():
        ran["v"] = True

    with pytest.raises(ApprovalRejected):
        asyncio.run(gate.wrap(async_dangerous)())
    assert ran["v"] is False
