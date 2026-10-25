from __future__ import annotations

import functools
import inspect
from typing import TYPE_CHECKING, Any

from .client import SentinelClient
from .config import get_config
from .exceptions import ApprovalRejected, ApprovalTimeout

if TYPE_CHECKING:
    from collections.abc import Callable

_PRIMITIVES = (str, int, float, bool, type(None))
_MAX_REPR = 500


def _truncate_repr(obj: Any) -> str:
    s = repr(obj)
    if len(s) > _MAX_REPR:
        return s[:_MAX_REPR] + "...<truncated>"
    return s


def _serialize_arguments(value: Any, path: str = "arguments") -> Any:
    """Return a JSON-safe copy of `value`, or raise TypeError.

    Raises the same exception type as SentinelClient.create_approval so the
    decorator, adapters and direct client all fail the same way, before any
    approval request is sent.
    """
    if isinstance(value, _PRIMITIVES):
        return value
    if isinstance(value, list | tuple):
        return [_serialize_arguments(v, f"{path}[{i}]") for i, v in enumerate(value)]
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if not isinstance(k, _PRIMITIVES):
                raise TypeError(
                    f"@oversight arguments must be JSON-serializable. "
                    f"{path} has a key of type {type(k).__name__}; keys must be str."
                )
            out[str(k)] = _serialize_arguments(v, f"{path}[{k!r}]")
        return out
    raise TypeError(
        f"@oversight arguments must be JSON-serializable. "
        f"{path} is of type {type(value).__name__}. "
        f"Convert sets to lists, bytes to base64 str, and objects to dicts "
        f"before the call."
    )


def _bound_arguments(fn: Callable, args: tuple, kwargs: dict) -> dict:
    signature = inspect.signature(fn)
    bound = signature.bind_partial(*args, **kwargs)
    bound.apply_defaults()
    return {
        name: _serialize_arguments(value, f"arguments[{name!r}]")
        for name, value in bound.arguments.items()
    }


def oversight(
    risk_level: str = "medium",
    approvers: list | None = None,
    timeout_seconds: float | None = None,
    fallback: str | None = None,
    idempotency_key: str | Callable[[], str] | None = None,
) -> Callable:
    def decorator(fn: Callable) -> Callable:
        is_async = inspect.iscoroutinefunction(fn)

        def _approval_kwargs() -> dict:
            """Extra kwargs for create_approval. Callable keys are invoked
            once per wrapped-function invocation."""
            if idempotency_key is None:
                return {}
            key = idempotency_key() if callable(idempotency_key) else idempotency_key
            return {"idempotency_key": key}

        if is_async:

            @functools.wraps(fn)
            async def awrapper(*args, **kwargs):
                cfg = get_config()
                client = SentinelClient(cfg)
                fb = fallback or cfg.fallback
                arguments = _bound_arguments(fn, args, kwargs)
                approval = await client.acreate_approval(
                    function_name=fn.__name__,
                    arguments=arguments,
                    risk_level=risk_level,
                    approvers=approvers,
                    timeout_seconds=timeout_seconds,
                    **_approval_kwargs(),
                )
                action_id = approval.get("action_id") or approval.get("id")
                try:
                    decision = await client.await_for_decision(action_id, timeout=timeout_seconds)
                except ApprovalTimeout:
                    if fb == "execute":
                        result = await fn(*args, **kwargs)
                        await client.aemit_audit_event(
                            action_id,
                            execution_result=_truncate_repr(result),
                            error="timeout-fallback-execute",
                        )
                        return result
                    raise

                status = decision.get("status") or decision.get("decision")
                if status == "approved":
                    try:
                        result = await fn(*args, **kwargs)
                    except Exception as e:
                        await client.aemit_audit_event(
                            action_id, execution_result=None, error=_truncate_repr(e)
                        )
                        raise
                    await client.aemit_audit_event(
                        action_id, execution_result=_truncate_repr(result)
                    )
                    return result
                if status == "rejected":
                    raise ApprovalRejected(reason=decision.get("reason", ""), action_id=action_id)
                raise ApprovalRejected(
                    reason=f"Unknown decision status: {status}", action_id=action_id
                )

            return awrapper

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            cfg = get_config()
            client = SentinelClient(cfg)
            fb = fallback or cfg.fallback
            arguments = _bound_arguments(fn, args, kwargs)
            approval = client.create_approval(
                function_name=fn.__name__,
                arguments=arguments,
                risk_level=risk_level,
                approvers=approvers,
                timeout_seconds=timeout_seconds,
                **_approval_kwargs(),
            )
            action_id = approval.get("action_id") or approval.get("id")
            try:
                decision = client.wait_for_decision(action_id, timeout=timeout_seconds)
            except ApprovalTimeout:
                if fb == "execute":
                    result = fn(*args, **kwargs)
                    client.emit_audit_event(
                        action_id,
                        execution_result=_truncate_repr(result),
                        error="timeout-fallback-execute",
                    )
                    return result
                raise

            status = decision.get("status") or decision.get("decision")
            if status == "approved":
                try:
                    result = fn(*args, **kwargs)
                except Exception as e:
                    client.emit_audit_event(
                        action_id, execution_result=None, error=_truncate_repr(e)
                    )
                    raise
                client.emit_audit_event(action_id, execution_result=_truncate_repr(result))
                return result
            if status == "rejected":
                raise ApprovalRejected(reason=decision.get("reason", ""), action_id=action_id)
            raise ApprovalRejected(reason=f"Unknown decision status: {status}", action_id=action_id)

        return wrapper

    return decorator
