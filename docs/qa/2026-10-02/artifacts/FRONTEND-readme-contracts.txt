UTC start: 2026-10-03T01:51:28+00:00
Command: rg -n -A 28 -B 5 'LangChain|CrewAI|AutoGen|LangGraph|Anthropic|OpenAI Agents|Semantic Kernel|async' README.md
Exit: 0

165-- `ApprovalRejected(reason, action_id)` — a human rejected the request.
166-- `ApprovalTimeout(action_id, timeout_seconds)` — no decision before deadline.
167-
168-## Async
169-
170:The decorator transparently supports `async def` functions:
171-
172-```python
173-@oversight(risk_level="medium", approvers=["alice@acme.com"])
174:async def send_email(to, body):
175-    await mailgun.send(to=to, body=body)
176-```
177-
178-## Audit log
179-
180-Every approval creates a hash-chained audit trail. Fetch it:
181-
182-```python
183-from sentinel import SentinelClient
184-client = SentinelClient()
185-events = client.list_audit_events(action_id="act_…")  # or omit for full log
186-```
187-
188-Each event has `prev_hash` and `event_hash` (SHA-256). Chain integrity can be
189-verified by recomputing `sha256(prev_hash + json(payload))`.
190-
191:## LangChain
192-
193-```python
194-from sentinel.adapters.langchain import SentinelCallbackHandler
195-
196-agent.run("…", callbacks=[SentinelCallbackHandler(risk_level="high")])
197-```
198-
199-Install with `pip install sentinel-oversight[langchain]`.
200-
201:## OpenAI Agents SDK
202-
203-```python
204-from agents import Agent, function_tool
205-from sentinel.adapters.openai_agents import gated
206-
207-@function_tool
208-def wire_transfer(amount: int, recipient: str) -> dict: ...
209-
210-agent = Agent(name="ops", tools=[gated(wire_transfer, risk_level="high")])
211-```
212-
213-No extra install needed — the adapter has no dependency on `openai-agents`.
214-
215:## Semantic Kernel
216-
217-```python
218-from semantic_kernel import Kernel
219-from sentinel.adapters.semantic_kernel import gate_kernel
220-
221-kernel = Kernel()
222-kernel.add_plugin(OpsPlugin(), plugin_name="ops")
223-
224-gate_kernel(kernel, risk_level="high", approvers=["ops@acme.com"])
225-# Every function the kernel invokes now pauses for Sentinel approval.
226-```
227-
228-Registers a function-invocation filter, so every `@kernel_function` runs
229-through Sentinel approval. Use `function_allowlist` / `function_denylist` to
230-scope which functions are gated. No extra install needed — the adapter has no
231-dependency on `semantic-kernel`.
232-
233-## Links
234-
235-- Website: <https://pauseapi.app>
236-- Dashboard: <https://app.pauseapi.app>
237-- API repo: <https://github.com/PetrefiedThunder/sentinel-api>
238-- This SDK: <https://github.com/PetrefiedThunder/sentinel-sdk>
239-
240-## License
241-
242-MIT
