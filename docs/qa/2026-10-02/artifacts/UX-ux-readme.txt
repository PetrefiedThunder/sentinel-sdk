UTC start: 2026-10-03T01:50:57+00:00
Command: nl -ba README.md
Exit: 0

     1	# Sentinel SDK (Python)
     2	
     3	[![PyPI version](https://img.shields.io/pypi/v/sentinel-oversight.svg)](https://pypi.org/project/sentinel-oversight/)
     4	[![Python](https://img.shields.io/pypi/pyversions/sentinel-oversight.svg)](https://pypi.org/project/sentinel-oversight/)
     5	[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
     6	[![Status](https://img.shields.io/badge/status-public%20beta-blue.svg)](https://pauseapi.app)
     7	
     8	**Oversight infrastructure for AI agents.**
     9	
    10	Sentinel adds human-in-the-loop approval to any Python function your agent calls.
    11	Wrap the function with `@oversight`, and the SDK pauses execution, requests
    12	approval, and only runs once a human approves.
    13	
    14	## Install
    15	
    16	```bash
    17	pip install sentinel-oversight
    18	```
    19	
    20	## Quick start
    21	
    22	```bash
    23	# 1. Create an account at https://app.pauseapi.app/signup
    24	#    Copy the API key it returns.
    25	
    26	# 2. Wrap your function:
    27	```
    28	
    29	```python
    30	from sentinel import configure, oversight
    31	
    32	configure(api_key="sk_live_…")
    33	
    34	@oversight(
    35	    risk_level="high",
    36	    approvers=["sms:+15551234567", "alice@acme.com"],
    37	    timeout_seconds=300,
    38	)
    39	def transfer_funds(amount: int, recipient: str):
    40	    return stripe.transfers.create(amount=amount, destination=recipient)
    41	```
    42	
    43	When your agent calls `transfer_funds(1000, "acct_xyz")`:
    44	1. Sentinel **pauses** execution and creates an approval on the backend.
    45	2. Notifications fire to every approver in the list (rules below).
    46	3. A human clicks **Approve** from a signed text/email link or the dashboard.
    47	4. The wrapped function **runs**, and its return value flows back to the caller.
    48	
    49	If rejected → `ApprovalRejected(reason)` is raised. If no response within
    50	`timeout_seconds` → `ApprovalTimeout` is raised (unless `fallback="execute"`).
    51	
    52	## Approver formats
    53	
    54	Each entry in `approvers=[...]` is a string. The format determines the channel.
    55	
    56	| Format                          | Channel | Example                            |
    57	|---------------------------------|---------|------------------------------------|
    58	| `name@company.com`              | Email   | `alice@acme.com`                   |
    59	| `mailto:name@company.com`       | Email (explicit) | `mailto:alice@acme.com`   |
    60	| `sms:+15551234567`              | SMS (Twilio) | `sms:+14155550123` — requires consent, see [SMS approvers](#sms-approvers--tcpa-consent) |
    61	
    62	You can mix formats — every approver receives a notification, the **first**
    63	decision wins.
    64	
    65	## Notification routing
    66	
    67	- **Email** — fires if `RESEND_API_KEY` is set AND any approver looks like an
    68	  email address. Email contains signed approve/reject links (HMAC-SHA256, scoped
    69	  to that action_id and timeout window).
    70	- **SMS** — fires if Twilio credentials are set AND an approver uses `sms:`.
    71	
    72	By default, emails send from `onboarding@resend.dev`. To get branded
    73	`approvals@yourdomain.app` email, verify your domain in Resend (Pro plan).
    74	
    75	## SMS approvers — TCPA consent
    76	
    77	To use `sms:+1...` approvers you must first register an opt-in record for each
    78	phone number. Sentinel won't create an approval whose approvers include an
    79	SMS destination without an active consent record — the API returns
    80	`400 SMS approver requires active SMS consent contact`.
    81	
    82	```python
    83	from sentinel import SentinelClient
    84	client = SentinelClient()
    85	
    86	# One-time, per phone number, after you've collected a real opt-in:
    87	client.register_sms_contact(
    88	    phone_number="+15551234567",
    89	    display_name="Maya (CTO)",
    90	    consent_source="onboarding_checkbox",       # e.g. "signed_form", "captured_web_form"
    91	    consent_note="Checked the SMS opt-in box during signup on 2026-05-25",
    92	)
    93	```
    94	
    95	Other helpers:
    96	```python
    97	client.list_sms_contacts()           # all active + revoked contacts for this tenant
    98	client.revoke_sms_contact("con_…")   # marks consent revoked; future SMS won't send
    99	```
   100	
   101	The customer can also reply **STOP** to any Sentinel SMS — the Twilio inbound
   102	webhook (`/webhooks/twilio/inbound`) automatically revokes their consent
   103	record. **HELP** returns a description and contact info. These two keywords
   104	are TCPA-mandated.
   105	
   106	## Default approvers
   107	
   108	If you don't want to pass `approvers=[...]` on every decorator, set a default
   109	on your tenant. The API falls back to the tenant's `default_approvers` when
   110	the caller's list is empty.
   111	
   112	```python
   113	from sentinel import SentinelClient
   114	client = SentinelClient()
   115	
   116	client.set_default_approvers(["sms:+15551234567", "ops@yourcompany.com"])
   117	# now any @oversight(...) call without approvers uses these
   118	```
   119	
   120	Read or override via the web UI at `https://app.pauseapi.app/contacts`.
   121	
   122	Resolution order when an approval is created:
   123	1. The caller's explicit `approvers=[...]` (if non-empty)
   124	2. The tenant's saved `default_approvers`
   125	3. The global `DEFAULT_APPROVERS` env var on the API
   126	4. 400 error if all three are empty
   127	
   128	## Risk levels
   129	
   130	`risk_level` is a string the dashboard uses for prioritization. Allowed values:
   131	`low`, `medium`, `high`, `critical`. Required.
   132	
   133	## Idempotency
   134	
   135	Pass `idempotency_key` to safely retry approval creation. The same tenant + key
   136	replays the original response; reusing a key with a different body returns 409.
   137	
   138	```python
   139	client.create_approval(
   140	    function_name="transfer_funds",
   141	    arguments={"amount": 100},
   142	    idempotency_key="transfer-2026-06-09-001",
   143	)
   144	```
   145	
   146	`@oversight(idempotency_key=...)` also accepts a callable, invoked once per call.
   147	
   148	## Configuration
   149	
   150	Set via `configure(...)` or environment variables:
   151	
   152	| Variable                | Default                         | Description                            |
   153	|-------------------------|---------------------------------|----------------------------------------|
   154	| `SENTINEL_API_URL`      | `https://api.pauseapi.app`      | Base URL of the Sentinel backend       |
   155	| `SENTINEL_API_KEY`      | _required_                      | Your tenant API key                    |
   156	| `SENTINEL_TIMEOUT`      | `300`                           | Default `timeout_seconds`              |
   157	| `SENTINEL_POLL_INTERVAL`| `2`                             | Seconds between status polls           |
   158	| `SENTINEL_FALLBACK`     | `reject`                        | `reject` or `execute` on timeout       |
   159	
   160	## Exceptions
   161	
   162	- `SentinelError` — base class for all Sentinel errors.
   163	- `SentinelConfigError` — SDK was used without an `api_key`.
   164	- `SentinelAPIError(status_code, message, url)` — backend returned a non-2xx.
   165	- `ApprovalRejected(reason, action_id)` — a human rejected the request.
   166	- `ApprovalTimeout(action_id, timeout_seconds)` — no decision before deadline.
   167	
   168	## Async
   169	
   170	The decorator transparently supports `async def` functions:
   171	
   172	```python
   173	@oversight(risk_level="medium", approvers=["alice@acme.com"])
   174	async def send_email(to, body):
   175	    await mailgun.send(to=to, body=body)
   176	```
   177	
   178	## Audit log
   179	
   180	Every approval creates a hash-chained audit trail. Fetch it:
   181	
   182	```python
   183	from sentinel import SentinelClient
   184	client = SentinelClient()
   185	events = client.list_audit_events(action_id="act_…")  # or omit for full log
   186	```
   187	
   188	Each event has `prev_hash` and `event_hash` (SHA-256). Chain integrity can be
   189	verified by recomputing `sha256(prev_hash + json(payload))`.
   190	
   191	## LangChain
   192	
   193	```python
   194	from sentinel.adapters.langchain import SentinelCallbackHandler
   195	
   196	agent.run("…", callbacks=[SentinelCallbackHandler(risk_level="high")])
   197	```
   198	
   199	Install with `pip install sentinel-oversight[langchain]`.
   200	
   201	## OpenAI Agents SDK
   202	
   203	```python
   204	from agents import Agent, function_tool
   205	from sentinel.adapters.openai_agents import gated
   206	
   207	@function_tool
   208	def wire_transfer(amount: int, recipient: str) -> dict: ...
   209	
   210	agent = Agent(name="ops", tools=[gated(wire_transfer, risk_level="high")])
   211	```
   212	
   213	No extra install needed — the adapter has no dependency on `openai-agents`.
   214	
   215	## Semantic Kernel
   216	
   217	```python
   218	from semantic_kernel import Kernel
   219	from sentinel.adapters.semantic_kernel import gate_kernel
   220	
   221	kernel = Kernel()
   222	kernel.add_plugin(OpsPlugin(), plugin_name="ops")
   223	
   224	gate_kernel(kernel, risk_level="high", approvers=["ops@acme.com"])
   225	# Every function the kernel invokes now pauses for Sentinel approval.
   226	```
   227	
   228	Registers a function-invocation filter, so every `@kernel_function` runs
   229	through Sentinel approval. Use `function_allowlist` / `function_denylist` to
   230	scope which functions are gated. No extra install needed — the adapter has no
   231	dependency on `semantic-kernel`.
   232	
   233	## Links
   234	
   235	- Website: <https://pauseapi.app>
   236	- Dashboard: <https://app.pauseapi.app>
   237	- API repo: <https://github.com/PetrefiedThunder/sentinel-api>
   238	- This SDK: <https://github.com/PetrefiedThunder/sentinel-sdk>
   239	
   240	## License
   241	
   242	MIT
