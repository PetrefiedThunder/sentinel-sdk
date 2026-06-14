"""Anthropic Claude tool-use adapter.

Wraps a dict mapping {tool_name: callable} so each tool execution pauses
for Sentinel approval before running. Drop-in replacement for the
manual `tool_use` loop you'd write against the Claude API.

    import anthropic
    from sentinel.adapters.anthropic import GatedToolExecutor

    def wire_transfer(amount: int, recipient: str) -> dict:
        return stripe.transfers.create(amount=amount, destination=recipient)

    def check_balance(account: str) -> dict:
        return {"balance": 12345}

    executor = GatedToolExecutor(
        tools={
            "wire_transfer": wire_transfer,   # gated
            "check_balance": check_balance,   # also gated by default
        },
        gated_tools={"wire_transfer"},        # only these require approval
        risk_level="high",
        approvers=["ops@acme.com"],
    )

    client = anthropic.Anthropic()
    response = client.messages.create(...)

    # When Claude returns a tool_use block, hand it to the executor:
    while response.stop_reason == "tool_use":
        tool_results = executor.run_tool_uses(response.content)
        response = client.messages.create(
            ...,
            messages=[
                ...previous,
                {"role": "assistant", "content": response.content},
                {"role": "user", "content": tool_results},
            ],
        )

The executor returns tool_result blocks ready to feed back into the API.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..client import SentinelClient
from ..exceptions import ApprovalRejected

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable


class GatedToolExecutor:
    """Executes Claude `tool_use` blocks with Sentinel approval gating.

    `gated_tools` controls which tool names require approval. If None,
    ALL tools are gated. If empty set, no tools are gated (no-op).
    """

    def __init__(
        self,
        tools: dict[str, Callable[..., Any]],
        *,
        gated_tools: Iterable[str] | None = None,
        client: SentinelClient | None = None,
        risk_level: str = "high",
        approvers: list[str] | None = None,
        timeout_seconds: float | None = None,
    ):
        self.tools = tools
        self.gated_tools: set[str] | None = set(gated_tools) if gated_tools is not None else None
        self.client = client or SentinelClient()
        self.risk_level = risk_level
        self.approvers = approvers
        self.timeout_seconds = timeout_seconds

    def _should_gate(self, tool_name: str) -> bool:
        if self.gated_tools is None:
            return True
        return tool_name in self.gated_tools

    def run_tool_uses(self, content_blocks: Any) -> list[dict[str, Any]]:
        """Process every tool_use block in `content_blocks` and return
        tool_result blocks in the same order. `content_blocks` is whatever
        the Anthropic SDK returned (.content); items can be dicts or the
        SDK's ToolUseBlock instances — we read by attribute or key."""
        results: list[dict[str, Any]] = []
        for block in content_blocks:
            block_type = _get(block, "type")
            if block_type != "tool_use":
                continue
            tool_use_id = _get(block, "id")
            tool_name = _get(block, "name")
            tool_input = _get(block, "input") or {}

            if tool_name not in self.tools:
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "is_error": True,
                        "content": f"No handler registered for tool '{tool_name}'.",
                    }
                )
                continue

            try:
                if self._should_gate(tool_name):
                    self._await_approval(tool_name, tool_input)
                output = self.tools[tool_name](**tool_input)
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": _stringify(output),
                    }
                )
            except ApprovalRejected as e:
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "is_error": True,
                        "content": f"Human approval was not granted: {e.reason}",
                    }
                )
            except Exception as e:
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "is_error": True,
                        "content": f"{type(e).__name__}: {e}",
                    }
                )

        return results

    def _await_approval(self, tool_name: str, tool_input: dict[str, Any]) -> None:
        approval = self.client.create_approval(
            function_name=tool_name,
            arguments=tool_input or {},
            risk_level=self.risk_level,
            approvers=self.approvers,
            timeout_seconds=self.timeout_seconds,
        )
        action_id = approval.get("action_id") or approval.get("id")
        decision = self.client.wait_for_decision(action_id, timeout=self.timeout_seconds)
        status = decision.get("status") or decision.get("decision")
        if status != "approved":
            raise ApprovalRejected(
                reason=decision.get("reason", "Tool execution not approved"),
                action_id=action_id,
            )


def _get(obj: Any, name: str) -> Any:
    """Read a field from either a dict or a Pydantic-style model."""
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        import json

        return json.dumps(value, default=str)
    except Exception:
        return str(value)
