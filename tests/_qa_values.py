"""Per-run random values for the QA suites.

No invented records: every identifier, credential and host here is generated
fresh on each run, and hosts are never resolved (tests/conftest.py blocks the
network; HTTP goes through httpx.MockTransport).
"""

import secrets
import uuid


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
