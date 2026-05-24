"""Sentinel SDK — oversight infrastructure for AI agents."""

from .client import SentinelClient
from .config import SentinelConfig, configure, get_config
from .decorator import oversight
from .exceptions import ApprovalRejected, ApprovalTimeout, SentinelConfigError, SentinelError

__version__ = "0.1.0"

__all__ = [
    "oversight",
    "SentinelClient",
    "SentinelConfig",
    "configure",
    "get_config",
    "SentinelError",
    "SentinelConfigError",
    "ApprovalRejected",
    "ApprovalTimeout",
    "__version__",
]
