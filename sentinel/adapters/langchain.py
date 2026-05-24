"""LangChain adapter for Sentinel.

Provides a callback handler that creates an approval request when a tool starts
and blocks until a decision is reached.
"""

from __future__ import annotations

from typing import Any, Optional

from ..client import SentinelClient
from ..exceptions import ApprovalRejected


class SentinelCallbackHandler:
    """LangChain callback handler that gates tool execution behind Sentinel approvals.

    Inherits from langchain_core.callbacks.BaseCallbackHandler at instantiation
    time so the langchain dependency stays optional.
    """

    def __new__(cls, *args, **kwargs):
        try:
            from langchain_core.callbacks import BaseCallbackHandler  # type: ignore
        except ImportError as e:
            raise ImportError(
                "langchain-core is required for SentinelCallbackHandler. "
                "Install with: pip install sentinel-oversight[langchain]"
            ) from e

        # Dynamically create a subclass mixing in BaseCallbackHandler.
        if not issubclass(cls, BaseCallbackHandler):
            new_cls = type(cls.__name__, (cls, BaseCallbackHandler), {})
            instance = object.__new__(new_cls)
            return instance
        return object.__new__(cls)

    def __init__(
        self,
        client: Optional[SentinelClient] = None,
        risk_level: str = "medium",
        approvers: Optional[list] = None,
        timeout_seconds: Optional[float] = None,
    ):
        self.client = client or SentinelClient()
        self.risk_level = risk_level
        self.approvers = approvers
        self.timeout_seconds = timeout_seconds

    def on_tool_start(
        self,
        serialized: dict,
        input_str: str,
        **kwargs: Any,
    ) -> None:
        tool_name = (serialized or {}).get("name", "unknown_tool")
        approval = self.client.create_approval(
            function_name=tool_name,
            arguments={"input": input_str},
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
