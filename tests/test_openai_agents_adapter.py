import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from sentinel.adapters.openai_agents import gated
from sentinel.exceptions import ApprovalRejected


class FakeFunctionTool:
    """Mimics agents.FunctionTool: name + async on_invoke_tool(ctx, args_json)."""

    def __init__(self, name, fn):
        self.name = name
        self._fn = fn

        async def on_invoke_tool(ctx, args_json):
            return self._fn(**json.loads(args_json or "{}"))

        self.on_invoke_tool = on_invoke_tool


def _approved_async_client():
    client = MagicMock()
    client.acreate_approval = AsyncMock(return_value={"action_id": "act_1"})
    client.await_for_decision = AsyncMock(return_value={"status": "approved"})
    return client


def _approved_sync_client():
    client = MagicMock()
    client.create_approval.return_value = {"action_id": "act_1"}
    client.wait_for_decision.return_value = {"status": "approved"}
    return client


def test_function_tool_approved_runs_and_returns():
    client = _approved_async_client()

    def search_web(query, limit=5):
        return {"query": query, "limit": limit}

    tool = FakeFunctionTool("search_web", search_web)
    gated_tool = gated(tool, client=client, risk_level="high")

    assert gated_tool is tool  # same object, callback swapped
    result = asyncio.run(tool.on_invoke_tool(None, json.dumps({"query": "cats", "limit": 3})))

    assert result == {"query": "cats", "limit": 3}
    client.acreate_approval.assert_awaited_once_with(
        function_name="search_web",
        arguments={"query": "cats", "limit": 3},
        risk_level="high",
        approvers=None,
        timeout_seconds=None,
    )
    client.await_for_decision.assert_awaited_once_with("act_1", timeout=None)


def test_function_tool_rejected_raises_and_tool_not_called():
    client = MagicMock()
    client.acreate_approval = AsyncMock(return_value={"action_id": "act_2"})
    client.await_for_decision = AsyncMock(
        return_value={"status": "rejected", "reason": "too risky"}
    )

    ran = {"v": False}

    def dangerous():
        ran["v"] = True
        return "done"

    tool = FakeFunctionTool("dangerous", dangerous)
    gated(tool, client=client)

    with pytest.raises(ApprovalRejected) as exc:
        asyncio.run(tool.on_invoke_tool(None, "{}"))
    assert "too risky" in str(exc.value)
    assert exc.value.action_id == "act_2"
    assert ran["v"] is False


def test_function_tool_empty_args_json():
    client = _approved_async_client()
    tool = FakeFunctionTool("noop", lambda: "ok")
    gated(tool, client=client)

    assert asyncio.run(tool.on_invoke_tool(None, "")) == "ok"
    assert client.acreate_approval.call_args.kwargs["arguments"] == {}


def test_plain_sync_callable_is_gated():
    client = _approved_sync_client()

    def wire_transfer(amount, recipient):
        return {"amount": amount, "recipient": recipient}

    wrapped = gated(wire_transfer, client=client, risk_level="critical")
    result = wrapped(amount=100, recipient="acct_9")

    assert result == {"amount": 100, "recipient": "acct_9"}
    client.create_approval.assert_called_once_with(
        function_name="wire_transfer",
        arguments={"amount": 100, "recipient": "acct_9"},
        risk_level="critical",
        approvers=None,
        timeout_seconds=None,
    )


def test_plain_sync_callable_rejected_raises():
    client = MagicMock()
    client.create_approval.return_value = {"action_id": "act_3"}
    client.wait_for_decision.return_value = {"status": "rejected", "reason": "nope"}

    ran = {"v": False}

    def dangerous():
        ran["v"] = True

    with pytest.raises(ApprovalRejected):
        gated(dangerous, client=client)()
    assert ran["v"] is False


def test_plain_async_callable_is_gated():
    client = _approved_async_client()

    async def async_tool(x):
        return x * 2

    wrapped = gated(async_tool, client=client)
    assert asyncio.iscoroutinefunction(wrapped)
    assert asyncio.run(wrapped(x=21)) == 42
    client.acreate_approval.assert_awaited_once()


def test_explicit_function_name_overrides_tool_name():
    client = _approved_async_client()
    tool = FakeFunctionTool("original", lambda: "ok")
    gated(tool, client=client, function_name="custom_name")

    asyncio.run(tool.on_invoke_tool(None, "{}"))
    assert client.acreate_approval.call_args.kwargs["function_name"] == "custom_name"


def test_non_tool_raises_type_error():
    with pytest.raises(TypeError):
        gated(object(), client=MagicMock())


def test_importable_without_openai_agents_installed():
    # The adapter must not import the `agents` package at module level —
    # importing the adapter must never pull in openai-agents.
    import sys

    import sentinel.adapters.openai_agents  # noqa: F401

    assert "agents" not in sys.modules
