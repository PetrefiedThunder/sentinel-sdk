"""FE-002: mixed-call approval inputs and existing payload compatibility."""

import asyncio
import functools
import inspect
from unittest.mock import AsyncMock, MagicMock

import pytest

from sentinel.adapters import autogen, crewai, langgraph, openai_agents
from sentinel.client import _ensure_json_serializable

CASES = [(name, False) for name in ("autogen", "crewai", "langgraph", "openai_agents")]
CASES += [(name, True) for name in ("autogen", "langgraph", "openai_agents")]


@pytest.fixture(params=CASES, ids=[f"{name}-{'async' if mode else 'sync'}" for name, mode in CASES])
def gated_call(request):
    adapter, asynchronous = request.param
    client = MagicMock()
    client.create_approval.return_value = {"action_id": "qa-action"}
    client.wait_for_decision.return_value = {"status": "approved"}
    client.acreate_approval = AsyncMock(return_value={"action_id": "qa-action"})
    client.await_for_decision = AsyncMock(return_value={"status": "approved"})

    def gate(fn):
        if asynchronous:
            original = fn

            @functools.wraps(original)
            async def fn(*args, **kwargs):
                return original(*args, **kwargs)

        if adapter == "autogen":
            wrapped = autogen.gated(client=client)(fn)
        elif adapter == "crewai":
            wrapped = crewai.gated(fn, client=client)
        elif adapter == "langgraph":
            wrapped = langgraph.SentinelToolGate(client=client).wrap(fn)
        else:
            wrapped = openai_agents.gated(fn, client=client)

        def invoke(*args, **kwargs):
            result = wrapped(*args, **kwargs)
            return asyncio.run(result) if asynchronous else result

        return invoke

    approval = client.acreate_approval if asynchronous else client.create_approval
    return gate, client, approval


def test_mixed_inputs_include_variadics_without_omitted_defaults(gated_call):
    gate, _, approval = gated_call

    def action(amount, /, *items, recipient, note="ordinary", **metadata):
        return amount, items, recipient, note, metadata

    assert gate(action)(10, "extra", recipient="recipient", currency="USD") == (
        10,
        ("extra",),
        "recipient",
        "ordinary",
        {"currency": "USD"},
    )
    assert approval.call_args.kwargs["arguments"] == {
        "amount": 10,
        "items": ("extra",),
        "recipient": "recipient",
        "metadata": {"currency": "USD"},
    }


@pytest.mark.parametrize("error", [TypeError, ValueError])
def test_unavailable_signature_preserves_keyword_collisions(gated_call, monkeypatch, error):
    gate, _, approval = gated_call

    def action(amount, **metadata):
        return amount, metadata

    wrapped = gate(action)

    def unavailable(_fn):
        raise error("signature unavailable")

    monkeypatch.setattr(inspect, "signature", unavailable)
    metadata = {"args": "keyword value", "kwargs": "other keyword value"}
    assert wrapped(10, **metadata) == (10, metadata)
    assert approval.call_args.kwargs["arguments"] == {"args": [10], "kwargs": metadata}


@pytest.mark.parametrize(
    "kwargs",
    [
        {"amount": 20, "recipient": "recipient"},
        {"unexpected": "value"},
        {"recipient": "recipient", "unexpected": "value"},
    ],
    ids=["duplicate", "missing-required", "unexpected"],
)
def test_invalid_mixed_binding_fails_before_approval(gated_call, kwargs):
    gate, client, _ = gated_call
    calls = []

    def action(amount, *, recipient):
        calls.append((amount, recipient))

    with pytest.raises(TypeError):
        gate(action)(10, **kwargs)
    assert calls == []
    client.create_approval.assert_not_called()
    client.acreate_approval.assert_not_called()
    client.wait_for_decision.assert_not_called()
    client.await_for_decision.assert_not_called()


@pytest.mark.parametrize(
    "args, kwargs, expected",
    [
        ((10, "recipient"), {}, {"args": [10, "recipient"]}),
        ((), {"amount": 10, "recipient": "recipient"}, {"amount": 10, "recipient": "recipient"}),
        ((), {}, {"args": []}),
    ],
    ids=["positional", "keyword", "empty"],
)
def test_nonmixed_payload_shape_remains_compatible(gated_call, args, kwargs, expected):
    gate, _, approval = gated_call

    def action(amount=10, recipient="recipient"):
        return amount, recipient

    assert gate(action)(*args, **kwargs) == (10, "recipient")
    assert approval.call_args.kwargs["arguments"] == expected


def test_mixed_binding_preserves_raw_values(gated_call):
    gate, _, approval = gated_call
    value = object()

    def action(payload, *, recipient):
        assert payload is value
        return recipient

    assert gate(action)(value, recipient="recipient") == "recipient"
    assert approval.call_args.kwargs["arguments"]["payload"] is value


def test_omitted_nonserializable_default_stays_out_of_approval(gated_call):
    """FE-002 must not add an unpassed internal dependency to the JSON payload."""
    gate, _, approval = gated_call
    dependency = object()

    def create_approval(**kwargs):
        _ensure_json_serializable(kwargs["arguments"])
        return {"action_id": "qa-action"}

    approval.side_effect = create_approval

    def action(amount, *, recipient, dependency=dependency):
        return amount, recipient, dependency

    result = gate(action)(10, recipient="recipient")
    assert result == (10, "recipient", dependency)
    assert result[2] is dependency
    assert approval.call_args.kwargs["arguments"] == {
        "amount": 10,
        "recipient": "recipient",
    }
