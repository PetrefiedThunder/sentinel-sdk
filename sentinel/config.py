import os
from dataclasses import dataclass, field, replace
from typing import Optional


def _default_api_url() -> str:
    return os.environ.get(
        "SENTINEL_API_URL",
        "https://sentinel-api-production-9c76.up.railway.app",
    )


def _default_api_key() -> Optional[str]:
    return os.environ.get("SENTINEL_API_KEY")


def _default_timeout() -> float:
    try:
        return float(os.environ.get("SENTINEL_TIMEOUT", "300"))
    except ValueError:
        return 300.0


def _default_fallback() -> str:
    return os.environ.get("SENTINEL_FALLBACK", "reject")


@dataclass
class SentinelConfig:
    api_url: str = field(default_factory=_default_api_url)
    api_key: Optional[str] = field(default_factory=_default_api_key)
    timeout_seconds: float = field(default_factory=_default_timeout)
    poll_interval: float = 2.0
    fallback: str = field(default_factory=_default_fallback)


_config: SentinelConfig = SentinelConfig()


def configure(**kwargs) -> SentinelConfig:
    """Mutate the module-global config."""
    global _config
    _config = replace(_config, **kwargs)
    return _config


def get_config() -> SentinelConfig:
    return _config
