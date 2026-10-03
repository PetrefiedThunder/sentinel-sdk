"""QA sweep: local adapter contracts; no provider or approval-service calls."""

import asyncio
import inspect
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from sentinel.adapters import anthropic, autogen, crewai, langgraph, openai_agents
from sentinel.adapters.semantic_kernel import sentinel_filter
from sentinel.client import SentinelClient
from sentinel.config import SentinelConfig
from sentinel.exceptions import ApprovalRejected, ApprovalTimeout, SentinelAPIError


def _client(decision):
    client = MagicMock()
    client.create_approval.return_value = {"action_id": "qa-action"}
    client.wait_for_decision.return_value = decision
    client.acreate_approval = AsyncMock(return_value={"action_id": "qa-action"})
    client.await_for_decision = AsyncMock(return_value=decision)
    return client


def _wrap(adapter, fn, client):
    if adapter == "autogen":
        return autogen.gated(client=client)(fn)
    if adapter == "crewai":
        return crewai.gated(fn, client=client)
    if adapter == "langgraph":
        return langgraph.SentinelToolGate(client=client).wrap(fn)
    return openai_agents.gated(fn, client=client)


def _invoke(adapter, client, fn):
    if adapter == "anthropic":
        return anthropic.GatedToolExecutor({"action": fn}, client=client).run_tool_uses(
            [{"type": "tool_use", "id": "qa-use", "name": "action", "input": {}}]
        )
    if adapter == "semantic_kernel":
        context = SimpleNamespace(function=SimpleNamespace(name="action"), arguments={})

        async def next_callback(_context):
            fn()

        return asyncio.run(sentinel_filter(client=client)(context, next_callback))
    if adapter == "langchain":
        pytest.importorskip("langchain_core")
        from sentinel.adapters.langchain import SentinelCallbackHandler

        SentinelCallbackHandler(client=client).on_tool_start({"name": "action"}, "{}")
        return fn()
    return _wrap(adapter, fn, client)()


@pytest.mark.parametrize(
    "adapter",
    [
        "anthropic",
        "autogen",
        "crewai",
        "langgraph",
        "openai_agents",
        "semantic_kernel",
        "langchain",
    ],
)
@pytest.mark.parametrize("decision", [{"status": "rejected"}, {"status": "unknown"}, {}, None])
def test_adapter_direct_invocation_does_not_execute_without_approval(adapter, decision):
    """Direct adapter gate must fail closed even on an invalid server response."""
    calls = []
    client = _client(decision)
    try:
        result = _invoke(adapter, client, lambda: calls.append("executed"))
    except (ApprovalRejected, AttributeError, TypeError):
        result = None
    assert calls == []
    if adapter == "anthropic":
        assert result[0]["is_error"] is True
        assert result[0]["tool_use_id"] == "qa-use"


@pytest.mark.parametrize(
    "adapter",
    [
        "anthropic",
        "autogen",
        "crewai",
        "langgraph",
        "openai_agents",
        "semantic_kernel",
        "langchain",
    ],
)
def test_adapter_direct_invocation_executes_once_after_approval(adapter):
    calls = []
    _invoke(adapter, _client({"status": "approved"}), lambda: calls.append("executed"))
    assert calls == ["executed"]


@pytest.mark.parametrize("adapter", ["autogen", "langgraph", "openai_agents"])
@pytest.mark.parametrize("decision", [{"status": "rejected"}, {"status": "unknown"}, {}])
def test_async_callable_rejection_preserves_semantics_and_stops_execution(adapter, decision):
    calls = []

    async def action(value: int) -> int:
        calls.append(value)
        return value

    client = _client(decision)
    wrapped = _wrap(adapter, action, client)
    assert inspect.iscoroutinefunction(wrapped)
    assert inspect.signature(wrapped) == inspect.signature(action)
    with pytest.raises(ApprovalRejected):
        asyncio.run(wrapped(value=5))
    assert calls == []
    client.create_approval.assert_not_called()
    client.acreate_approval.assert_awaited_once()


@pytest.mark.parametrize("adapter", ["autogen", "crewai", "langgraph", "openai_agents"])
def test_mixed_sync_arguments_are_fully_presented_for_approval(adapter):
    """FE-002: approval must include both positional and keyword inputs."""
    client = _client({"status": "approved"})

    def action(amount: int, *, recipient: str):
        return amount, recipient

    assert _wrap(adapter, action, client)(90000, recipient="qa-recipient") == (
        90000,
        "qa-recipient",
    )
    assert client.create_approval.call_args.kwargs["arguments"] == {
        "amount": 90000,
        "recipient": "qa-recipient",
    }


@pytest.mark.parametrize("adapter", ["autogen", "langgraph", "openai_agents"])
def test_mixed_async_arguments_are_fully_presented_for_approval(adapter):
    """FE-002: async approval must include positional and keyword inputs."""
    client = _client({"status": "approved"})

    async def action(amount: int, *, recipient: str):
        return amount, recipient

    assert asyncio.run(_wrap(adapter, action, client)(90000, recipient="qa-recipient")) == (
        90000,
        "qa-recipient",
    )
    assert client.acreate_approval.call_args.kwargs["arguments"] == {
        "amount": 90000,
        "recipient": "qa-recipient",
    }


@pytest.mark.parametrize("asynchronous", [False, True], ids=["invoke", "ainvoke"])
@pytest.mark.parametrize("failure", ["rejected", "timeout", "transport_error"])
def test_real_langchain_tool_does_not_run_after_gate_failure(asynchronous, failure):
    """FE-001: a gate error must propagate through the host without execution."""
    pytest.importorskip("langchain_core")
    from langchain_core.tools import tool

    from sentinel.adapters.langchain import SentinelCallbackHandler

    calls = []

    @tool
    def local_action(value: int) -> str:
        """Record a local action without contacting any external service."""
        calls.append(value)
        return "executed"

    client = _client({"status": "rejected", "reason": "qa denied"})
    error = ApprovalRejected
    if failure == "timeout":
        client.wait_for_decision.side_effect = ApprovalTimeout("qa-action", 1)
        error = ApprovalTimeout
    elif failure == "transport_error":
        client.create_approval.side_effect = ConnectionError("qa local connection failure")
        error = ConnectionError
    config = {"callbacks": [SentinelCallbackHandler(client=client)]}
    with pytest.raises(error):
        if asynchronous:
            asyncio.run(local_action.ainvoke({"value": 7}, config=config))
        else:
            local_action.invoke({"value": 7}, config=config)
    client.create_approval.assert_called_once()
    assert calls == []


@pytest.mark.parametrize("asynchronous", [False, True], ids=["invoke", "ainvoke"])
@pytest.mark.parametrize("stage", ["create", "wait"])
@pytest.mark.parametrize(
    "failure, error",
    [
        ("network", httpx.ConnectError),
        ("timeout", httpx.ReadTimeout),
        ("invalid_json", ValueError),
        ("null", AttributeError),
        ("array", AttributeError),
        ("http_403", SentinelAPIError),
        ("http_503", SentinelAPIError),
    ],
)
def test_real_langchain_http_gate_failures_block_execution(asynchronous, stage, failure, error):
    """FE-001: use the real HTTP client and host with an offline transport."""
    pytest.importorskip("langchain_core")
    from langchain_core.tools import tool

    from sentinel.adapters.langchain import SentinelCallbackHandler

    calls = []
    requests = []

    @tool
    def local_action(value: int) -> str:
        """Record a local action without contacting any external service."""
        calls.append(value)
        return "executed"

    def transport(request):
        requests.append(request.url.path)
        if stage == "wait" and request.method == "POST":
            return httpx.Response(201, json={"action_id": "qa-action"})
        if failure == "network":
            raise httpx.ConnectError("synthetic connection failure", request=request)
        if failure == "timeout":
            raise httpx.ReadTimeout("synthetic timeout", request=request)
        if failure == "invalid_json":
            return httpx.Response(200, content=b"not JSON")
        if failure == "null":
            return httpx.Response(200, content=b"null")
        if failure == "array":
            return httpx.Response(200, json=[])
        return httpx.Response(int(failure.removeprefix("http_")), json={"detail": "denied"})

    client = SentinelClient(SentinelConfig(api_url="https://sentinel.invalid"))
    with httpx.Client(
        base_url="https://sentinel.invalid", transport=httpx.MockTransport(transport)
    ) as http_client:
        client._client = http_client
        handler = SentinelCallbackHandler(client=client)
        assert handler.raise_error is True
        config = {"callbacks": [handler]}
        with pytest.raises(error):
            if asynchronous:
                asyncio.run(local_action.ainvoke({"value": 7}, config=config))
            else:
                local_action.invoke({"value": 7}, config=config)
    assert requests == (
        ["/v1/approvals"]
        if stage == "create"
        else ["/v1/approvals", "/v1/approvals/qa-action/wait"]
    )
    assert calls == []


@pytest.mark.parametrize("asynchronous", [False, True], ids=["invoke", "ainvoke"])
def test_real_langchain_approved_tool_executes_once(asynchronous):
    pytest.importorskip("langchain_core")
    from langchain_core.tools import tool

    from sentinel.adapters.langchain import SentinelCallbackHandler

    calls = []

    @tool
    def local_action(value: int) -> str:
        """Record a local action without contacting any external service."""
        calls.append(value)
        return "executed"

    client = _client({"status": "approved"})
    config = {"callbacks": [SentinelCallbackHandler(client=client)]}
    if asynchronous:
        result = asyncio.run(local_action.ainvoke({"value": 7}, config=config))
    else:
        result = local_action.invoke({"value": 7}, config=config)
    assert result == "executed"
    assert calls == [7]
    client.create_approval.assert_called_once()
    client.wait_for_decision.assert_called_once_with("qa-action", timeout=None)


@pytest.mark.parametrize("block_style", ["mapping", "model"])
def test_anthropic_unknown_tool_and_non_tool_blocks_are_safe(block_style):
    client = _client({"status": "approved"})
    blocks = [
        {"type": "text", "text": "ignore"},
        {"type": "tool_use", "id": "qa-use", "name": "missing", "input": {}},
    ]
    if block_style == "model":
        blocks = [SimpleNamespace(**block) for block in blocks]
    results = anthropic.GatedToolExecutor({}, client=client).run_tool_uses(blocks)
    assert len(results) == 1
    assert results[0]["is_error"] is True
    assert results[0]["tool_use_id"] == "qa-use"
    client.create_approval.assert_not_called()


@pytest.mark.parametrize("args_json", ["not json", "[]", "null", "7", "{}"])
def test_openai_function_tool_rejection_blocks_malformed_and_valid_inputs(args_json):
    original = AsyncMock(return_value="executed")
    tool = SimpleNamespace(name="action", on_invoke_tool=original)
    client = _client({"status": "rejected"})
    assert openai_agents.gated(tool, client=client) is tool
    with pytest.raises(ApprovalRejected):
        asyncio.run(tool.on_invoke_tool(None, args_json))
    original.assert_not_awaited()


def test_crewai_run_object_keeps_identity_and_rejection_blocks_original():
    original = MagicMock(return_value="executed")
    tool = SimpleNamespace(name="action", _run=original)
    assert crewai.gated(tool, client=_client({"status": "rejected"})) is tool
    with pytest.raises(ApprovalRejected):
        tool._run(value=1)
    original.assert_not_called()
