"""CrewAI adapter — wrap a CrewAI tool with Sentinel approval.

CrewAI tools are typically built with @tool() or BaseTool. Wrap them with
`gated()` to require human approval before each invocation:

    from crewai import Agent, Task, Crew
    from crewai.tools import tool
    from sentinel.adapters.crewai import gated

    @tool("wire_transfer")
    def _wire_transfer(amount: int, recipient: str) -> dict:
        return stripe.transfers.create(amount=amount, destination=recipient)

    wire_transfer = gated(
        _wire_transfer,
        risk_level="high",
        approvers=["ops@acme.com"],
    )

    agent = Agent(tools=[wire_transfer], ...)

The adapter wraps the underlying callable so CrewAI calls it normally —
Sentinel intercepts inside the wrapper and pauses for human approval.
"""
from __future__ import annotations

from typing import Any, Callable, Optional

from ..client import SentinelClient
from ..exceptions import ApprovalRejected


def gated(
    tool: Any,
    *,
    client: Optional[SentinelClient] = None,
    risk_level: str = "high",
    approvers: Optional[list[str]] = None,
    timeout_seconds: Optional[float] = None,
    function_name: Optional[str] = None,
) -> Any:
    """Wrap a CrewAI tool (BaseTool instance or @tool-decorated callable)
    so each invocation pauses for Sentinel approval.

    Returns an object with the same external interface — CrewAI can call
    it exactly like the original tool.
    """
    sentinel_client = client or SentinelClient()
    derived_name = function_name or _derive_tool_name(tool)

    original = _extract_callable(tool)

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        # CrewAI tools are usually called with kwargs; fall back to positional.
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
        return original(*args, **kwargs)

    # Preserve the CrewAI BaseTool object if we were handed one — only
    # swap out the underlying _run / func reference.
    if hasattr(tool, "_run") and callable(tool._run):
        tool._run = wrapper  # type: ignore[attr-defined]
        return tool
    if hasattr(tool, "func") and callable(tool.func):
        tool.func = wrapper  # type: ignore[attr-defined]
        return tool
    # Plain callable — return the wrapper directly
    wrapper.__name__ = getattr(original, "__name__", derived_name)
    return wrapper


def _extract_callable(tool: Any) -> Callable:
    if hasattr(tool, "_run") and callable(tool._run):
        return tool._run
    if hasattr(tool, "func") and callable(tool.func):
        return tool.func
    if callable(tool):
        return tool
    raise TypeError(
        f"Don't know how to extract a callable from {type(tool).__name__}. "
        "Pass a CrewAI BaseTool instance or a @tool-decorated function."
    )


def _derive_tool_name(tool: Any) -> str:
    for attr in ("name", "tool_name", "__name__"):
        value = getattr(tool, attr, None)
        if isinstance(value, str) and value:
            return value
    return "crewai_tool"
