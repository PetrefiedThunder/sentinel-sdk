from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable


def approval_arguments(fn: Callable, args: tuple, kwargs: dict) -> dict[str, Any]:
    """Include both argument sets while preserving existing nonmixed payloads."""
    if not args or not kwargs:
        return kwargs if kwargs else {"args": list(args)}

    try:
        signature = inspect.signature(fn)
    except (TypeError, ValueError):
        return {"args": list(args), "kwargs": kwargs}

    bound = signature.bind(*args, **kwargs)
    return dict(bound.arguments)
