# Sentinel SDK

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI version](https://img.shields.io/badge/pypi-v0.1.0-blue.svg)](https://pypi.org/project/sentinel-oversight/)

**Oversight infrastructure for AI agents.**

Sentinel adds human-in-the-loop approval to any Python function your agent calls.
Wrap the function with `@oversight`, and the SDK pauses execution, requests
approval, and only runs once a human approves.

## Install

```bash
pip install sentinel-oversight
```

## Quick start

```python
from sentinel import configure, oversight

configure(api_key="sk_live_...")

@oversight(
    risk_level="high",
    approvers=["sms:+15551234567"],
    timeout_seconds=300,
)
def transfer_funds(amount: int, recipient: str):
    return stripe.transfers.create(amount=amount, destination=recipient)
```

When your agent calls `transfer_funds(1000, "acct_xyz")`, Sentinel pauses
execution, texts an approval request, and only runs the function once a human
approves it. If rejected, `ApprovalRejected` is raised. If no response
within `timeout_seconds`, `ApprovalTimeout` is raised (unless `fallback="execute"`).

## Configuration

Set via `configure(...)` or env vars:

- `SENTINEL_API_URL` (default `https://api.pauseapi.app`)
- `SENTINEL_API_KEY`
- `SENTINEL_TIMEOUT` (default `300`)
- `SENTINEL_FALLBACK` (default `reject`)

## LangChain

```python
from sentinel.adapters.langchain import SentinelCallbackHandler

agent.run("...", callbacks=[SentinelCallbackHandler(risk_level="high")])
```

Install with `pip install sentinel-oversight[langchain]`.

## Links

- Website: https://pauseapi.app
- API repo: https://github.com/PetrefiedThunder/sentinel-api
- This SDK: https://github.com/PetrefiedThunder/sentinel-sdk

## License

MIT
