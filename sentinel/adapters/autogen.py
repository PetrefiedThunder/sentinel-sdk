"""AutoGen adapter — wrap a function registered with AutoGen so each call
pauses for Sentinel approval.

Works with both classic AutoGen (`pyautogen` / `autogen-agentchat`) and the
newer `autogen-core` — anywhere you register a Python callable as a tool.

    from autogen_agentchat.agents import AssistantAgent
    from sentinel.adapters.autogen import gated

    @gated(risk_level="high", approvers=["ops@acme.com"])
    def wire_transfer(amount: int, recipient: str) -> dict:
        return stripe.transfers.create(amount=amount, destination=recipient)

    agent = AssistantAgent(tools=[wire_transfer], ...)

Async functions are supported transparently — the returned wrapper preserves
sync vs. async semantics of the original.
"""
from __future__ import annotations

import asyncio
import functools
from typing import Any, Callable, Optional

from ..client import SentinelClient
from ..exceptions import ApprovalRejected


def gated(
    *,
    client: Optional[SentinelClient] = None,
    risk_level: str = "high",
    approvers: Optional[list[str]] = None,
    timeout_seconds: Optional[float] = None,
    function_name: Optional[str] = None,
) -> Callable[[Callable], Callable]:
    """Decorator that gates an AutoGen-registered function behind Sentinel."""
    def decorator(fn: Callable) -> Callable:
        sentinel_client = client or SentinelClient()
        derived_name = function_name or getattr(fn, "__name__", "autogen_tool")

        if asyncio.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                arguments = kwargs if kwargs else {"args": list(args)}
                approval = await sentinel_client.acreate_approval(
                    function_name=derived_name,
                    arguments=arguments,
                    risk_level=risk_level,
                    approvers=approvers,
                    timeout_seconds=timeout_seconds,
                )
                action_id = approval.get("action_id") or approval.get("id")
                decision = await sentinel_client.await_for_decision(
                    action_id, timeout=timeout_seconds
                )
                status = decision.get("status") or decision.get("decision")
                if status != "approved":
                    raise ApprovalRejected(
                        reason=decision.get("reason", "Tool execution not approved"),
                        action_id=action_id,
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
            decision = sentinel_client.wait_for_decision(
                action_id, timeout=timeout_seconds
            )
            status = decision.get("status") or decision.get("decision")
            if status != "approved":
                raise ApprovalRejected(
                    reason=decision.get("reason", "Tool execution not approved"),
                    action_id=action_id,
                )
            return fn(*args, **kwargs)

        return sync_wrapper

    return decorator
