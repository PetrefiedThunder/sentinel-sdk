# Pass 2: adapter integration and packaging QA

PR: opened by orchestrator

CI status: pending at time of writing

This repository is a Python SDK with no frontend application. Adapter integration is the closest useful frontend lens: the host framework is where an SDK approval decision becomes a tool side effect. Browser builds, Playwright flows, cross-browser smoke, Lighthouse, WCAG/axe, mobile layout and UI screenshots do not apply. Saved command reports provide the evidence instead. Package build, isolated wheel installation and static checks are recorded by the QA lead in the combined report.

## Scope and methods

- Highest risk: a denied, timed-out or failed approval must never permit the host tool to execute. Direct unit tests alone cannot establish that contract, so this pass uses real local LangChain `StructuredTool.invoke` and `ainvoke` calls with a mocked approval client.
- Next risk: the approval request must describe every executed input. Boundary cases mix positional and keyword arguments, cover synchronous/asynchronous wrappers and preserve callable metadata where supported.
- The test pyramid consists of 35 direct adapter decision checks across all seven adapters, nine async rejection/metadata checks, eight real local LangChain host cases, and 15 additional argument/protocol/object checks. All 67 cases avoid external API calls.
- FE-A exploratory charter: maximum 15 minutes; actual UTC window 01:51:13–01:53:25 on 2026-10-03. Check rejection, timeout, malformed decisions and host callback semantics. Exit early after both high-priority defects were demonstrated.
- FE-B exploratory charter: maximum 10 minutes; verify test quality, reported host behavior, proposed mitigation, and evidence links. Finish once focused tests and static checks pass with known defects expected to fail.

## Results

`tests/test_qa_adapters.py`: **54 passed, 13 xfailed**, zero skips in the QA environment. All expected failures are strict and carry a finding ID; unrelated exceptions will fail normally. LangChain-specific tests use `pytest.importorskip` so the ordinary SDK dev installation does not require the optional host package.

The 13 expected failures comprise six FE-001 rejection/timeout/transport-error cases over `invoke` and `ainvoke`, plus seven FE-002 mixed-input cases over four adapters. Explicitly disabling expected-failure handling for two representative cases produced **2 failed**, demonstrating that the tests expose the defects rather than pass vacuously. Ruff lint passes. The initial format check failed on the newly added file; formatting that test file fixed it without modifying product code.

Evidence:

- [Final focused results](artifacts/FRONTEND-focused-final.txt)
- [Unsuppressed failing reproductions](artifacts/FRONTEND-negative-control.txt)
- [LangChain callback source and version evidence](artifacts/FRONTEND-langchain-source-evidence.txt)
- [Test-only suggested-fix control](artifacts/FRONTEND-suggested-fix-control.txt)
- [Test lint](artifacts/FRONTEND-formatted-test-check.txt)
- [Complete timestamped pass log](FRONTEND-LOG.md)

## Findings

| ID | Severity | Group | Title | Exact repro steps | Expected vs actual | Evidence | Suggested fix |
|---|---|---|---|---|---|---|---|
| FE-001 | Critical | Frontend substitute / adapter integration | LangChain executes tools after approval rejection, timeout or transport failure | With `langchain-core==1.6.6` installed, run `.venv/bin/python -m pytest --runxfail -q 'tests/test_qa_adapters.py::test_real_langchain_tool_does_not_run_after_gate_failure[rejected-invoke]'`. The test uses a real local LangChain tool, installs `SentinelCallbackHandler` in its callbacks, and returns a rejected decision from the mocked approval service. Other parameters repeat with `ainvoke`, timeout and connection error. | Expected: no tool execution and an error propagated. Actual: the callback creates the approval and raises, but the host logs the callback exception and executes the tool; local side-effect list becomes `[7]`. | `sentinel/adapters/langchain.py:15`, `:65`, `:67`; `tests/test_qa_adapters.py:171`; [red reproduction](artifacts/FRONTEND-negative-control.txt); installed `BaseCallbackHandler.raise_error=False` and callback-manager catch/continue shown in [host evidence](artifacts/FRONTEND-langchain-source-evidence.txt). | Configure the handler to propagate callback errors (`raise_error=True`) and retain real-host rejection/failure tests over supported LangChain versions. A test-only instance override stopped both sync and async local tool calls in the saved control. No product fix applied. |
| FE-002 | High | Frontend substitute / adapter integration | Mixed positional/keyword calls hide execution arguments from approval | Run `.venv/bin/python -m pytest --runxfail -q 'tests/test_qa_adapters.py::test_mixed_sync_arguments_are_fully_presented_for_approval[autogen]'`. Wrap `action(amount, *, recipient)` and call it with positional `90000` and keyword `recipient='qa-recipient'`. Repeat for CrewAI, LangGraph and plain OpenAI Agents wrappers, and async variants where supported. | Expected: the approval payload contains `amount=90000` and `recipient`. Actual: only `recipient` is submitted for approval; the tool subsequently receives and executes with the unreviewed amount. | `sentinel/adapters/autogen.py:51`, `:75`; `sentinel/adapters/crewai.py:59`; `sentinel/adapters/langgraph.py:75`, `:99`; `sentinel/adapters/openai_agents.py:109`, `:124`; `tests/test_qa_adapters.py:126`, `:148`; [red reproduction](artifacts/FRONTEND-negative-control.txt). | Bind args and kwargs to the callable signature before serializing an approval request; preserve both argument sets for callables without an inspectable signature. Share the binding behavior across adapters and retain mixed-call regressions. No product fix applied. |

## Verified safe behavior and limits

Direct gates for all seven adapters stop execution on rejected, unknown, empty and non-dictionary decisions. This is explicitly **not** a claim that every real host honors the gate: LangChain demonstrates why that distinction matters. AutoGen, LangGraph and OpenAI plain async wrappers preserve coroutine status/signatures and do not use the synchronous approval methods. Anthropic ignores non-tool blocks and reports unknown tools without requesting approval. OpenAI FunctionTool-shaped callbacks stop malformed JSON/scalar/list inputs after rejection. CrewAI-shaped `_run` objects retain identity and block their original callback on rejection.

Real host testing was limited to **Python 3.11.15 and langchain-core 1.6.6**. Other adapters were exercised through their actual SDK wrappers with plain functions, `SimpleNamespace` host-shaped objects and async callbacks, not installed CrewAI, AutoGen, OpenAI Agents, LangGraph, Anthropic or Semantic Kernel runtimes. No model/provider requests or hosted approval service were used. Host version compatibility, framework scheduling/cancellation, streaming, actual remote approval semantics and browser accessibility are not established by these results. Existing/added SDK-wide coverage and packaging evidence are consolidated in `COVERAGE.md` and `SUMMARY.md`.

Counts for this pass: Critical=1 High=1 Medium=0 Low=0.

Recommended fix order: FE-001 first, then FE-002. Both affect the integrity of approval enforcement, so passing unit counts do not establish release readiness.
