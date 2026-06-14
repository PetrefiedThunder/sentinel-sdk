"""Semantic Kernel adapter — gate kernel function/tool invocation behind
Sentinel approval.

Semantic Kernel (the `semantic-kernel` package) runs every `KernelFunction`
through a *function-invocation filter* pipeline. A filter is an async callable
``(context, next)`` where calling ``await next(context)`` executes the function;
not calling it skips execution. That makes filters the natural place to pause
for human approval before any plugin/@kernel_function runs.

    from semantic_kernel import Kernel
    from sentinel.adapters.semantic_kernel import gate_kernel

    kernel = Kernel()
    kernel.add_plugin(OpsPlugin(), plugin_name="ops")

    gate_kernel(kernel, risk_level="high", approvers=["ops@acme.com"])
    # Every function the kernel invokes now pauses for Sentinel approval.

Use ``function_allowlist`` to gate only specific functions, or
``function_denylist`` to exempt specific ones; ungated functions call through
directly with no approval round-trip. Names are matched against both the bare
function name (e.g. ``wire_transfer``) and the qualified ``plugin.function``
form (e.g. ``ops.wire_transfer``).

If you build the filter yourself, ``sentinel_filter()`` returns the raw filter
callable to register via ``kernel.add_filter(FilterTypes.FUNCTION_INVOCATION, ...)``
or the ``@kernel.filter`` decorator.

This module never imports `semantic-kernel`, so it works without the package
installed and across versions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Iterable

from ..client import SentinelClient
from ..exceptions import ApprovalRejected


def gate_kernel(
    kernel: Any,
    *,
    client: SentinelClient | None = None,
    risk_level: str = "high",
    approvers: list[str] | None = None,
    timeout_seconds: float | None = None,
    function_allowlist: Iterable[str] | None = None,
    function_denylist: Iterable[str] | None = None,
) -> Any:
    """Register a Sentinel function-invocation filter on a Semantic Kernel
    ``Kernel`` so each function invocation pauses for human approval.

    Returns the same ``kernel`` object so calls can be chained. The kernel is
    passed in untyped — this adapter never imports ``semantic-kernel``.
    """
    sk_filter = sentinel_filter(
        client=client,
        risk_level=risk_level,
        approvers=approvers,
        timeout_seconds=timeout_seconds,
        function_allowlist=function_allowlist,
        function_denylist=function_denylist,
    )
    # `FilterTypes.FUNCTION_INVOCATION` == "function_invocation"; add_filter
    # accepts the enum or its string value, so pass the string to avoid
    # importing semantic-kernel here.
    kernel.add_filter("function_invocation", sk_filter)
    return kernel


def sentinel_filter(
    *,
    client: SentinelClient | None = None,
    risk_level: str = "high",
    approvers: list[str] | None = None,
    timeout_seconds: float | None = None,
    function_allowlist: Iterable[str] | None = None,
    function_denylist: Iterable[str] | None = None,
) -> Callable[[Any, Callable[[Any], Awaitable[None]]], Awaitable[None]]:
    """Build a Semantic Kernel function-invocation filter that requires
    Sentinel approval before each gated function runs.

    The returned async callable matches Semantic Kernel's filter signature
    ``async def filter(context, next)`` and can be registered with
    ``kernel.add_filter(FilterTypes.FUNCTION_INVOCATION, ...)`` or the
    ``@kernel.filter(FilterTypes.FUNCTION_INVOCATION)`` decorator.
    """
    sentinel_client = client or SentinelClient()
    allow = set(function_allowlist) if function_allowlist is not None else None
    deny = set(function_denylist) if function_denylist is not None else None

    def _should_gate(name: str, qualified_name: str) -> bool:
        if allow is not None:
            return name in allow or qualified_name in allow
        if deny is not None:
            return name not in deny and qualified_name not in deny
        return True

    async def filter(context: Any, next: Callable[[Any], Awaitable[None]]) -> None:
        name = _function_name(context)
        qualified_name = _qualified_function_name(context)
        if not _should_gate(name, qualified_name):
            await next(context)
            return

        approval = await sentinel_client.acreate_approval(
            function_name=qualified_name,
            arguments=_arguments(context),
            risk_level=risk_level,
            approvers=approvers,
            timeout_seconds=timeout_seconds,
        )
        action_id = approval.get("action_id") or approval.get("id")
        decision = await sentinel_client.await_for_decision(action_id, timeout=timeout_seconds)
        status = decision.get("status") or decision.get("decision")
        if status != "approved":
            raise ApprovalRejected(
                reason=decision.get("reason", "Function execution not approved"),
                action_id=action_id,
            )
        await next(context)

    return filter


def _function_name(context: Any) -> str:
    function = getattr(context, "function", None)
    name = getattr(function, "name", None)
    if isinstance(name, str) and name:
        return name
    return "semantic_kernel_function"


def _qualified_function_name(context: Any) -> str:
    function = getattr(context, "function", None)
    name = _function_name(context)
    plugin = getattr(function, "plugin_name", None)
    if isinstance(plugin, str) and plugin:
        return f"{plugin}.{name}"
    return name


def _arguments(context: Any) -> dict[str, Any]:
    """KernelArguments behaves like a mapping; coerce it to a plain JSON-safe
    dict, dropping the non-serializable execution-settings entry SK adds."""
    arguments = getattr(context, "arguments", None)
    if arguments is None:
        return {}
    try:
        items = dict(arguments)
    except (TypeError, ValueError):
        return {"args": str(arguments)}
    return {k: v for k, v in items.items() if k != "execution_settings"}
