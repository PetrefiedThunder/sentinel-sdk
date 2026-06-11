"""OpenAI Agents SDK adapter — wrap an Agents SDK tool with Sentinel approval.

Tools in the OpenAI Agents SDK (`openai-agents` package) are typically built
with @function_tool, which produces a FunctionTool whose async
`on_invoke_tool(ctx, args_json)` callback executes the tool. Wrap a tool with
`gated()` to require human approval before each invocation:

    from agents import Agent, Runner, function_tool
    from sentinel.adapters.openai_agents import gated

    @function_tool
    def wire_transfer(amount: int, recipient: str) -> dict:
        return stripe.transfers.create(amount=amount, destination=recipient)

    agent = Agent(
        name="ops",
        tools=[gated(wire_transfer, risk_level="high", approvers=["ops@acme.com"])],
    )
    result = Runner.run_sync(agent, "...")

The adapter swaps the tool's `on_invoke_tool` callback for one that pauses
for Sentinel approval, so the Agents SDK calls the tool normally. Plain
callables (functions not yet wrapped by @function_tool) are also accepted —
they get the same gating applied directly. This module never imports
`openai-agents`, so it works without the package installed and across
versions.
"""

from __future__ import annotations

import asyncio
import functools
import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

from ..client import SentinelClient
from ..exceptions import ApprovalRejected


def gated(
    tool: Any,
    *,
    client: SentinelClient | None = None,
    risk_level: str = "high",
    approvers: list[str] | None = None,
    timeout_seconds: float | None = None,
    function_name: str | None = None,
) -> Any:
    """Wrap an OpenAI Agents SDK tool (FunctionTool instance or plain
    callable) so each invocation pauses for Sentinel approval.

    Returns the same FunctionTool object with its `on_invoke_tool` callback
    gated, or a gated wrapper if a plain callable was passed.
    """
    sentinel_client = client or SentinelClient()
    derived_name = function_name or _derive_tool_name(tool)

    if hasattr(tool, "on_invoke_tool") and callable(tool.on_invoke_tool):
        original = tool.on_invoke_tool

        @functools.wraps(original)
        async def gated_invoke(ctx: Any, args_json: str) -> Any:
            arguments = _parse_arguments(args_json)
            await _arequire_approval(
                sentinel_client,
                derived_name,
                arguments,
                risk_level=risk_level,
                approvers=approvers,
                timeout_seconds=timeout_seconds,
            )
            return await original(ctx, args_json)

        tool.on_invoke_tool = gated_invoke
        return tool

    if callable(tool):
        return _wrap_plain_callable(
            tool,
            sentinel_client,
            derived_name,
            risk_level=risk_level,
            approvers=approvers,
            timeout_seconds=timeout_seconds,
        )

    raise TypeError(
        f"Don't know how to gate {type(tool).__name__}. "
        "Pass a FunctionTool (from @function_tool) or a plain callable."
    )


def _wrap_plain_callable(
    fn: Callable,
    sentinel_client: SentinelClient,
    derived_name: str,
    *,
    risk_level: str,
    approvers: list[str] | None,
    timeout_seconds: float | None,
) -> Callable:
    if asyncio.iscoroutinefunction(fn):

        @functools.wraps(fn)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            arguments = kwargs if kwargs else {"args": list(args)}
            await _arequire_approval(
                sentinel_client,
                derived_name,
                arguments,
                risk_level=risk_level,
                approvers=approvers,
                timeout_seconds=timeout_seconds,
            )
            return await fn(*args, **kwargs)

        return async_wrapper

    @functools.wraps(fn)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        arguments = kwargs if kwargs else {"args": list(args)}
        approval = sentinel_client.create_approval(
            function_name=derived_name,
            arguments=arguments,
            risk_level=risk_level,
            approvers=approvers,
            timeout_seconds=timeout_seconds,
        )
        action_id = approval.get("action_id") or approval.get("id")
        decision = sentinel_client.wait_for_decision(action_id, timeout=timeout_seconds)
        status = decision.get("status") or decision.get("decision")
        if status != "approved":
            raise ApprovalRejected(
                reason=decision.get("reason", "Tool execution not approved"),
                action_id=action_id,
            )
        return fn(*args, **kwargs)

    return sync_wrapper


async def _arequire_approval(
    sentinel_client: SentinelClient,
    derived_name: str,
    arguments: dict[str, Any],
    *,
    risk_level: str,
    approvers: list[str] | None,
    timeout_seconds: float | None,
) -> None:
    approval = await sentinel_client.acreate_approval(
        function_name=derived_name,
        arguments=arguments,
        risk_level=risk_level,
        approvers=approvers,
        timeout_seconds=timeout_seconds,
    )
    action_id = approval.get("action_id") or approval.get("id")
    decision = await sentinel_client.await_for_decision(action_id, timeout=timeout_seconds)
    status = decision.get("status") or decision.get("decision")
    if status != "approved":
        raise ApprovalRejected(
            reason=decision.get("reason", "Tool execution not approved"),
            action_id=action_id,
        )


def _parse_arguments(args_json: Any) -> dict[str, Any]:
    """on_invoke_tool receives the tool arguments as a JSON string."""
    if isinstance(args_json, dict):
        return args_json
    if not args_json:
        return {}
    try:
        parsed = json.loads(args_json)
    except (TypeError, ValueError):
        return {"raw": str(args_json)}
    if isinstance(parsed, dict):
        return parsed
    return {"args": parsed}


def _derive_tool_name(tool: Any) -> str:
    for attr in ("name", "tool_name", "__name__"):
        value = getattr(tool, attr, None)
        if isinstance(value, str) and value:
            return value
    return "openai_agents_tool"
