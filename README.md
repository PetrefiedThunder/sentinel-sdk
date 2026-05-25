# Sentinel SDK

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI version](https://img.shields.io/pypi/v/sentinel-oversight.svg)](https://pypi.org/project/sentinel-oversight/)

**Oversight infrastructure for AI agents.**

Sentinel adds human-in-the-loop approval to any Python function your agent calls.
Wrap the function with `@oversight`, and the SDK pauses execution, requests
approval, and only runs once a human approves.

## Install

```bash
pip install sentinel-oversight
```

## Quick start

```bash
# 1. Create an account at https://app.pauseapi.app/signup
#    Copy the API key it returns.

# 2. Wrap your function:
```

```python
from sentinel import configure, oversight

configure(api_key="sk_live_…")

@oversight(
    risk_level="high",
    approvers=["sms:+15551234567", "alice@acme.com"],
    timeout_seconds=300,
)
def transfer_funds(amount: int, recipient: str):
    return stripe.transfers.create(amount=amount, destination=recipient)
```

When your agent calls `transfer_funds(1000, "acct_xyz")`:
1. Sentinel **pauses** execution and creates an approval on the backend.
2. Notifications fire to every approver in the list (rules below).
3. A human clicks **Approve** from a signed text/email link or the dashboard.
4. The wrapped function **runs**, and its return value flows back to the caller.

If rejected → `ApprovalRejected(reason)` is raised. If no response within
`timeout_seconds` → `ApprovalTimeout` is raised (unless `fallback="execute"`).

## Approver formats

Each entry in `approvers=[...]` is a string. The format determines the channel.

| Format                          | Channel | Example                            |
|---------------------------------|---------|------------------------------------|
| `name@company.com`              | Email   | `alice@acme.com`                   |
| `mailto:name@company.com`       | Email (explicit) | `mailto:alice@acme.com`   |
| `sms:+15551234567`              | SMS (Twilio) | `sms:+14155550123` — requires consent, see [SMS approvers](#sms-approvers--tcpa-consent) |

You can mix formats — every approver receives a notification, the **first**
decision wins.

## Notification routing

- **Email** — fires if `RESEND_API_KEY` is set AND any approver looks like an
  email address. Email contains signed approve/reject links (HMAC-SHA256, scoped
  to that action_id and timeout window).
- **SMS** — fires if Twilio credentials are set AND an approver uses `sms:`.

By default, emails send from `onboarding@resend.dev`. To get branded
`approvals@yourdomain.app` email, verify your domain in Resend (Pro plan).

## SMS approvers — TCPA consent

To use `sms:+1...` approvers you must first register an opt-in record for each
phone number. Sentinel won't create an approval whose approvers include an
SMS destination without an active consent record — the API returns
`400 SMS approver requires active SMS consent contact`.

```python
from sentinel import SentinelClient
client = SentinelClient()

# One-time, per phone number, after you've collected a real opt-in:
client.register_sms_contact(
    phone_number="+15551234567",
    display_name="Maya (CTO)",
    consent_source="onboarding_checkbox",       # e.g. "signed_form", "captured_web_form"
    consent_note="Checked the SMS opt-in box during signup on 2026-05-25",
)
```

Other helpers:
```python
client.list_sms_contacts()           # all active + revoked contacts for this tenant
client.revoke_sms_contact("con_…")   # marks consent revoked; future SMS won't send
```

The customer can also reply **STOP** to any Sentinel SMS — the Twilio inbound
webhook (`/webhooks/twilio/inbound`) automatically revokes their consent
record. **HELP** returns a description and contact info. These two keywords
are TCPA-mandated.

## Risk levels

`risk_level` is a string the dashboard uses for prioritization. Allowed values:
`low`, `medium`, `high`, `critical`. Required.

## Configuration

Set via `configure(...)` or environment variables:

| Variable                | Default                         | Description                            |
|-------------------------|---------------------------------|----------------------------------------|
| `SENTINEL_API_URL`      | `https://api.pauseapi.app`      | Base URL of the Sentinel backend       |
| `SENTINEL_API_KEY`      | _required_                      | Your tenant API key                    |
| `SENTINEL_TIMEOUT`      | `300`                           | Default `timeout_seconds`              |
| `SENTINEL_POLL_INTERVAL`| `2`                             | Seconds between status polls           |
| `SENTINEL_FALLBACK`     | `reject`                        | `reject` or `execute` on timeout       |

## Exceptions

- `SentinelError` — base class for all Sentinel errors.
- `SentinelConfigError` — SDK was used without an `api_key`.
- `SentinelAPIError(status_code, message, url)` — backend returned a non-2xx.
- `ApprovalRejected(reason, action_id)` — a human rejected the request.
- `ApprovalTimeout(action_id, timeout_seconds)` — no decision before deadline.

## Async

The decorator transparently supports `async def` functions:

```python
@oversight(risk_level="medium", approvers=["alice@acme.com"])
async def send_email(to, body):
    await mailgun.send(to=to, body=body)
```

## Audit log

Every approval creates a hash-chained audit trail. Fetch it:

```python
from sentinel import SentinelClient
client = SentinelClient()
events = client.list_audit_events(action_id="act_…")  # or omit for full log
```

Each event has `prev_hash` and `event_hash` (SHA-256). Chain integrity can be
verified by recomputing `sha256(prev_hash + json(payload))`.

## LangChain

```python
from sentinel.adapters.langchain import SentinelCallbackHandler

agent.run("…", callbacks=[SentinelCallbackHandler(risk_level="high")])
```

Install with `pip install sentinel-oversight[langchain]`.

## Links

- Website: <https://pauseapi.app>
- Dashboard: <https://app.pauseapi.app>
- API repo: <https://github.com/PetrefiedThunder/sentinel-api>
- This SDK: <https://github.com/PetrefiedThunder/sentinel-sdk>

## License

MIT
