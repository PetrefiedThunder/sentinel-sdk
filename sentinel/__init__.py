"""Sentinel SDK — oversight infrastructure for AI agents."""

from .client import PageResult, SentinelClient
from .config import SentinelConfig, configure, get_config
from .decorator import oversight
from .exceptions import (
    ApprovalRejected,
    ApprovalTimeout,
    SentinelAPIError,
    SentinelConfigError,
    SentinelError,
)

__version__ = "0.1.9"

__all__ = [
    "oversight",
    "SentinelClient",
    "PageResult",
    "SentinelConfig",
    "configure",
    "get_config",
    "SentinelError",
    "SentinelAPIError",
    "SentinelConfigError",
    "ApprovalRejected",
    "ApprovalTimeout",
    "__version__",
]
