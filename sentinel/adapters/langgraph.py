"""LangGraph adapter — gate tool executions in a LangGraph graph behind
Sentinel approval.

`SentinelToolGate` wraps plain Python callables (the functions you pass to
graph nodes or tool nodes), so this adapter never imports langgraph and has
zero dependencies on it — it works with any LangGraph version.

    from sentinel.adapters.langgraph import SentinelToolGate

    gate = SentinelToolGate(risk_level="high", approvers=["ops@acme.com"])

    def my_tool_fn(state):
        return run_dangerous_thing(state)

    graph.add_node("tools", gate.wrap(my_tool_fn))

Async functions are supported transparently — the returned wrapper preserves
sync vs. async semantics of the original. Use `tool_allowlist` to gate only
specific tools, or `tool_denylist` to exempt specific tools; ungated tools
call through directly with no approval round-trip.
"""
from __future__ import annotations

import asyncio
import functools
from typing import Any, Callable, Iterable, Optional

from ..client import SentinelClient
from ..exceptions import ApprovalRejected


class SentinelToolGate:
    """Wraps LangGraph node/tool callables so each call pauses for Sentinel
    approval before executing."""

    def __init__(
        self,
        client: Optional[SentinelClient] = None,
        risk_level: str = "high",
        approvers: Optional[list[str]] = None,
        timeout_seconds: Optional[float] = None,
        tool_allowlist: Optional[Iterable[str]] = None,
        tool_denylist: Optional[Iterable[str]] = None,
    ):
        self.client = client or SentinelClient()
        self.risk_level = risk_level
        self.approvers = approvers
        self.timeout_seconds = timeout_seconds
        self.tool_allowlist = set(tool_allowlist) if tool_allowlist is not None else None
        self.tool_denylist = set(tool_denylist) if tool_denylist is not None else None

    def _should_gate(self, tool_name: str) -> bool:
        if self.tool_allowlist is not None:
            return tool_name in self.tool_allowlist
        if self.tool_denylist is not None:
            return tool_name not in self.tool_denylist
        return True

    def wrap(self, fn: Callable, function_name: Optional[str] = None) -> Callable:
        """Return a wrapper around ``fn`` that requires Sentinel approval
        before each invocation. Preserves sync vs. async semantics."""
        derived_name = function_name or getattr(fn, "__name__", "langgraph_tool")

        if not self._should_gate(derived_name):
            return fn

        if asyncio.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                arguments = kwargs if kwargs else {"args": list(args)}
                approval = await self.client.acreate_approval(
                    function_name=derived_name,
                    arguments=arguments,
                    risk_level=self.risk_level,
                    approvers=self.approvers,
                    timeout_seconds=self.timeout_seconds,
                )
                action_id = approval.get("action_id") or approval.get("id")
                decision = await self.client.await_for_decision(
                    action_id, timeout=self.timeout_seconds
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
            approval = self.client.create_approval(
                function_name=derived_name,
                arguments=arguments,
                risk_level=self.risk_level,
                approvers=self.approvers,
                timeout_seconds=self.timeout_seconds,
            )
            action_id = approval.get("action_id") or approval.get("id")
            decision = self.client.wait_for_decision(
                action_id, timeout=self.timeout_seconds
            )
            status = decision.get("status") or decision.get("decision")
            if status != "approved":
                raise ApprovalRejected(
                    reason=decision.get("reason", "Tool execution not approved"),
                    action_id=action_id,
                )
            return fn(*args, **kwargs)

        return sync_wrapper
