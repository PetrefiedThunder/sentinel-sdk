"""Per-run random values for the QA suites.

No invented records: every identifier, credential and host here is generated
fresh on each run, and hosts are never resolved (tests/conftest.py blocks the
network; HTTP goes through httpx.MockTransport).
"""

import secrets
import uuid

from sentinel.config import SentinelConfig


def rid() -> str:
    return str(uuid.uuid4())


def rhex(n: int = 16) -> str:
    return secrets.token_hex(n)


def rhost() -> str:
    return f"h{secrets.token_hex(8)}.h{secrets.token_hex(4)}"


ACTION_ID = rid()
USE_ID = rid()
RECIPIENT = rid()
TRANSFER_ID = rid()
ACCOUNT_ID = rid()
REQUEST_IDS = {"one": rid(), "two": rid()}
REPLAY_KEY = rid()
API_KEYS = {"one": rhex(), "two": rhex()}
HOSTS = {"one": rhost(), "two": rhost()}
DX_HOST = rhost()
DX_KEY = rhex()
CREDENTIAL_MARKER = rhex()
ERR_DETAIL = rhex()
ERR_TRANSPORT = rhex()
ERR_OPERATION = rhex()
RESULT_TEXT = rhex()
ERROR_TEXT = rhex()


def ramount() -> int:
    return secrets.randbelow(10**6) + 1


def rname() -> str:
    return f"t_{secrets.token_hex(6)}"


def rseconds() -> float:
    """A positive duration with two decimals, fresh per run."""
    return (secrets.randbelow(10**5) + 1) / 100


def rseconds_except(*taken: float) -> float:
    """A fresh duration that never equals any of ``taken`` (e.g. a config default)."""
    while True:
        value = rseconds()
        if value not in taken:
            return value


def rclock() -> float:
    """A monotonic-clock reading, fresh per run."""
    return float(secrets.randbelow(10**9) + 1)


# Defaults read from the SDK itself so overrides are always distinguishable.
_DEFAULTS = SentinelConfig(api_key=None)

AMOUNTS = {"one": ramount(), "two": ramount()}
CURRENCY = rhex(3)
NOTE = rhex()
ITEM = rhex()
TOOL_NAME = rname()
MISSING_TOOL = rname()
TASK_NAME = rname()
CONTACT_ID = rid()
META = {"args": rhex(), "kwargs": rhex()}
TIMEOUT_SECONDS = rseconds_except(_DEFAULTS.timeout_seconds)
POLL_SECONDS = rseconds_except(_DEFAULTS.poll_interval)
JSON_NUMBER = str(ramount())
