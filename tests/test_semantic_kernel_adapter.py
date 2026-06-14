import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from sentinel.adapters.semantic_kernel import gate_kernel, sentinel_filter
from sentinel.exceptions import ApprovalRejected


class FakeFunction:
    """Mimics semantic_kernel KernelFunction: name + plugin_name."""

    def __init__(self, name, plugin_name=None):
        self.name = name
        self.plugin_name = plugin_name


class FakeContext:
    """Mimics semantic_kernel.filters.FunctionInvocationContext."""

    def __init__(self, function, arguments=None):
        self.function = function
        self.arguments = arguments or {}
        self.result = None


def _approved_client():
    client = MagicMock()
    client.acreate_approval = AsyncMock(return_value={"action_id": "act_1"})
    client.await_for_decision = AsyncMock(return_value={"status": "approved"})
    return client


def _run_filter(sk_filter, context):
    """Drive an SK filter with a `next` that records whether the function ran."""
    ran = {"v": False}

    async def next_callback(ctx):
        ran["v"] = True
        ctx.result = "executed"

    asyncio.run(sk_filter(context, next_callback))
    return ran["v"]


def test_approved_runs_function():
    client = _approved_client()
    sk_filter = sentinel_filter(client=client, risk_level="high")
    ctx = FakeContext(FakeFunction("wire_transfer", "ops"), {"amount": 100, "recipient": "acct_9"})

    assert _run_filter(sk_filter, ctx) is True
    assert ctx.result == "executed"
    client.acreate_approval.assert_awaited_once_with(
        function_name="ops.wire_transfer",
        arguments={"amount": 100, "recipient": "acct_9"},
        risk_level="high",
        approvers=None,
        timeout_seconds=None,
    )
    client.await_for_decision.assert_awaited_once_with("act_1", timeout=None)


def test_rejected_raises_and_function_not_called():
    client = MagicMock()
    client.acreate_approval = AsyncMock(return_value={"action_id": "act_2"})
    client.await_for_decision = AsyncMock(
        return_value={"status": "rejected", "reason": "too risky"}
    )
    sk_filter = sentinel_filter(client=client)
    ctx = FakeContext(FakeFunction("dangerous"))

    ran = {"v": False}

    async def next_callback(c):
        ran["v"] = True

    with pytest.raises(ApprovalRejected) as exc:
        asyncio.run(sk_filter(ctx, next_callback))
    assert "too risky" in str(exc.value)
    assert exc.value.action_id == "act_2"
    assert ran["v"] is False


def test_unqualified_name_used_when_no_plugin():
    client = _approved_client()
    sk_filter = sentinel_filter(client=client)
    ctx = FakeContext(FakeFunction("lookup"))

    _run_filter(sk_filter, ctx)
    assert client.acreate_approval.call_args.kwargs["function_name"] == "lookup"


def test_allowlist_unlisted_function_calls_through():
    client = _approved_client()
    sk_filter = sentinel_filter(client=client, function_allowlist=["wire_transfer"])
    ctx = FakeContext(FakeFunction("harmless", "ops"))

    assert _run_filter(sk_filter, ctx) is True
    client.acreate_approval.assert_not_awaited()
    client.await_for_decision.assert_not_awaited()


def test_allowlist_matches_qualified_name():
    client = _approved_client()
    sk_filter = sentinel_filter(client=client, function_allowlist=["ops.wire_transfer"])
    ctx = FakeContext(FakeFunction("wire_transfer", "ops"))

    assert _run_filter(sk_filter, ctx) is True
    client.acreate_approval.assert_awaited_once()


def test_denylist_listed_function_skips_approval():
    client = _approved_client()
    sk_filter = sentinel_filter(client=client, function_denylist=["read_only_lookup"])
    ctx = FakeContext(FakeFunction("read_only_lookup", "data"))

    assert _run_filter(sk_filter, ctx) is True
    client.acreate_approval.assert_not_awaited()


def test_arguments_drop_execution_settings():
    client = _approved_client()
    sk_filter = sentinel_filter(client=client)
    ctx = FakeContext(
        FakeFunction("act", "ops"),
        {"amount": 5, "execution_settings": object()},
    )

    _run_filter(sk_filter, ctx)
    assert client.acreate_approval.call_args.kwargs["arguments"] == {"amount": 5}


def test_gate_kernel_registers_filter_and_returns_kernel():
    client = _approved_client()
    kernel = MagicMock()

    returned = gate_kernel(kernel, client=client, risk_level="critical")

    assert returned is kernel
    kernel.add_filter.assert_called_once()
    filter_type, registered = kernel.add_filter.call_args.args
    assert filter_type == "function_invocation"
    assert callable(registered)

    # The registered filter actually gates: run it and confirm approval flow.
    ctx = FakeContext(FakeFunction("change_state", "lights"), {"id": 1})
    assert _run_filter(registered, ctx) is True
    client.acreate_approval.assert_awaited_once_with(
        function_name="lights.change_state",
        arguments={"id": 1},
        risk_level="critical",
        approvers=None,
        timeout_seconds=None,
    )


def test_importable_without_semantic_kernel_installed():
    # The adapter must not import the `semantic_kernel` package at module
    # level — importing the adapter must never pull it in.
    import sys

    import sentinel.adapters.semantic_kernel  # noqa: F401

    assert "semantic_kernel" not in sys.modules
