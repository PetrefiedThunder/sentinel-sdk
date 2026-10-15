# Frontend QA substitute: adapter integration and packaging

This Python SDK has no browser UI. Browser, WCAG, responsive-layout, console/network and Lighthouse checks do not apply; adapter host integration is the useful frontend boundary. All execution is local with mocked approval clients.
# Pass 2: Adapter and packaging QA

All timestamps UTC.

- **2026-10-03T01:50:34+00:00 → 2026-10-03T01:50:34+00:00** `pwd` — exit **0**; [output](artifacts/FRONTEND-identity.txt).

- **2026-10-03T01:50:39+00:00 → 2026-10-03T01:50:39+00:00** `rg --files -g '!uv.lock' -g '!*.lock' -g '!.env*' -g '!docs/qa/**'` — exit **0**; [output](artifacts/FRONTEND-file-map.txt).

- **2026-10-03T01:50:39+00:00 → 2026-10-03T01:50:39+00:00** `python3 -c 'import subprocess; [(print(x), subprocess.run(x.split(), check=False)) for x in ["git worktree list", "git status --short --branch", "git remote -v"]]'` — exit **0**; [output](artifacts/FRONTEND-git-identity.txt).

- **2026-10-03T01:50:46+00:00 → 2026-10-03T01:50:46+00:00** `rg --files --hidden -g AGENTS.md -g '!docs/qa/**' -g '!.git/**'` — exit **1**; [output](artifacts/FRONTEND-instructions.txt).

- **2026-10-03T01:50:46+00:00 → 2026-10-03T01:50:46+00:00** `python3 -c 'from pathlib import Path; files=[Path("pyproject.toml"),*Path("tests").glob("test_*adapter.py")]; [(print("\nFILE",str(p)),print(p.read_text())) for p in files]'` — exit **0**; [output](artifacts/FRONTEND-test-config.txt).

- **2026-10-03T01:50:46+00:00 → 2026-10-03T01:50:46+00:00** `python3 -c 'from pathlib import Path; files=list(Path("sentinel/adapters").glob("*.py")); [(print("\nFILE",str(p)),print("".join(f"{i}: {s}" for i,s in enumerate(p.open(),1)))) for p in files]'` — exit **0**; [output](artifacts/FRONTEND-adapter-source.txt).

- **2026-10-03T01:50:50+00:00 → 2026-10-03T01:50:50+00:00** `python3 -c 'from pathlib import Path; files=["sentinel/adapters/langchain.py","sentinel/adapters/anthropic.py","sentinel/adapters/openai_agents.py","sentinel/adapters/langgraph.py"]; [(print("\nFILE",p),print("".join(f"{i}: {s}" for i,s in enumerate(Path(p).open(),1)))) for p in files]'` — exit **0**; [output](artifacts/FRONTEND-focused-source.txt).

- **2026-10-03T01:51:00+00:00 → 2026-10-03T01:51:00+00:00** `python3 -c 'from pathlib import Path; from datetime import datetime, timezone; print(datetime.now(timezone.utc).isoformat()); print(Path("docs/qa/2026-10-02/artifacts/qa_run.py").read_text())'` — exit **0**; [output](artifacts/FRONTEND-logger-and-time.txt).

- **2026-10-03T01:51:13+00:00** Charter FE-A (15-minute timebox): prove host-framework callbacks stop side effects after rejection/error; exercise all seven adapters across approved, rejected, unknown and malformed decisions. Inspect metadata and mixed-argument fidelity. Exit with focused regressions and evidence; real defects remain strict expected failures.

- **2026-10-03T01:51:13+00:00 → 2026-10-03T01:51:13+00:00** `python3 -c 'from pathlib import Path; from datetime import datetime, timezone; p=Path("docs/qa/2026-10-02/FRONTEND-LOG.md"); stamp=datetime.now(timezone.utc).isoformat(timespec="seconds"); p.write_text("# Frontend QA substitute: adapter integration and packaging\n\nThis Python SDK has no browser UI. Browser, WCAG, responsive-layout, console/network and Lighthouse checks do not apply; adapter host integration is the useful frontend boundary. All execution is local with mocked approval clients.\n" + p.read_text() + f"\n- **{stamp}** Charter FE-A (15-minute timebox): prove host-framework callbacks stop side effects after rejection/error; exercise all seven adapters across approved, rejected, unknown and malformed decisions. Inspect metadata and mixed-argument fidelity. Exit with focused regressions and evidence; real defects remain strict expected failures.\n")'` — exit **0**; [output](artifacts/FRONTEND-start-charter.txt).

- **2026-10-03T01:51:25+00:00 → 2026-10-03T01:51:25+00:00** `python3 -c 'from pathlib import Path; print("python exists:",Path(".venv3.11/bin/python").exists()); print("pytest exists:",Path(".venv3.11/bin/pytest").exists())'` — exit **0**; [output](artifacts/FRONTEND-environment-check.txt).

- **2026-10-03T01:51:28+00:00 → 2026-10-03T01:51:28+00:00** `rg -n -A 28 -B 5 'LangChain|CrewAI|AutoGen|LangGraph|Anthropic|OpenAI Agents|Semantic Kernel|async' README.md` — exit **0**; [output](artifacts/FRONTEND-readme-contracts.txt).

- **2026-10-03T01:52:31+00:00** Tool edit: added tests/test_qa_adapters.py using apply_patch. All-seven direct-gate matrix, sync/async metadata, Anthropic unknown-tool output, OpenAI malformed-input rejection, CrewAI object identity; strict expected-failure regressions for FE-001 host fail-open and FE-002 incomplete approval arguments. No product source changed.

- **2026-10-03T01:52:31+00:00 → 2026-10-03T01:52:31+00:00** `python3 -c 'from pathlib import Path; from datetime import datetime, timezone; stamp=datetime.now(timezone.utc).isoformat(timespec="seconds"); p=Path("docs/qa/2026-10-02/FRONTEND-LOG.md"); p.open("a").write(f"\n- **{stamp}** Tool edit: added tests/test_qa_adapters.py using apply_patch. All-seven direct-gate matrix, sync/async metadata, Anthropic unknown-tool output, OpenAI malformed-input rejection, CrewAI object identity; strict expected-failure regressions for FE-001 host fail-open and FE-002 incomplete approval arguments. No product source changed.\n"); print(Path("sentinel/exceptions.py").read_text())'` — exit **0**; [output](artifacts/FRONTEND-log-test-edit.txt).

- **2026-10-03T01:52:31+00:00 → 2026-10-03T01:52:31+00:00** `.venv/bin/python -m pytest tests/test_qa_adapters.py -q -ra` — exit **0**; [output](artifacts/FRONTEND-adapter-tests.txt).

- **2026-10-03T01:52:58+00:00 → 2026-10-03T01:52:58+00:00** `.venv/bin/python -m pytest --runxfail -q 'tests/test_qa_adapters.py::test_real_langchain_tool_does_not_run_after_gate_failure[rejected-invoke]' 'tests/test_qa_adapters.py::test_mixed_sync_arguments_are_fully_presented_for_approval[autogen]'` — exit **1**; [output](artifacts/FRONTEND-negative-control.txt).

- **2026-10-03T01:52:58+00:00 → 2026-10-03T01:52:58+00:00** `.venv/bin/python -c 'import inspect; from langchain_core.callbacks import BaseCallbackHandler; from langchain_core.callbacks import manager; import importlib.metadata; print("langchain-core",importlib.metadata.version("langchain-core")); print("BaseCallbackHandler.raise_error:",BaseCallbackHandler.raise_error); print("manager:",inspect.getsourcefile(manager)); source,start=inspect.getsourcelines(manager.handle_event); print("".join(f"{i}: {line}" for i,line in enumerate(source,start)))'` — exit **0**; [output](artifacts/FRONTEND-langchain-source-evidence.txt).

- **2026-10-03T01:53:25+00:00** Charter FE-A completed early after 9 minutes: direct adapter gate checks pass, but actual LangChain invoke/ainvoke execute after rejection, timeout or transport failure (FE-001). Four callable adapters omit positional input whenever keyword arguments exist (FE-002). Intentional --runxfail negative control exits 1 with both failures.
- **2026-10-03T01:53:25+00:00** Tool edit: imported ApprovalTimeout in tests, allowed its propagation in host regression, verified callback invocation, and added approved LangChain invoke/ainvoke controls via apply_patch.
- **2026-10-03T01:53:25+00:00** Charter FE-B (10-minute timebox): verify focused test quality, adapter error/malformed contract coverage and artifact reproducibility; inspect host signature/in-place wrapping limits without expanding to heavy framework installation. Root owns build/static/package auditing.

- **2026-10-03T01:53:25+00:00 → 2026-10-03T01:53:25+00:00** `python3 -c 'from pathlib import Path; from datetime import datetime, timezone; stamp=datetime.now(timezone.utc).isoformat(timespec="seconds"); Path("docs/qa/2026-10-02/FRONTEND-LOG.md").open("a").write(f"\n- **{stamp}** Charter FE-A completed early after 9 minutes: direct adapter gate checks pass, but actual LangChain invoke/ainvoke execute after rejection, timeout or transport failure (FE-001). Four callable adapters omit positional input whenever keyword arguments exist (FE-002). Intentional --runxfail negative control exits 1 with both failures.\n- **{stamp}** Tool edit: imported ApprovalTimeout in tests, allowed its propagation in host regression, verified callback invocation, and added approved LangChain invoke/ainvoke controls via apply_patch.\n- **{stamp}** Charter FE-B (10-minute timebox): verify focused test quality, adapter error/malformed contract coverage and artifact reproducibility; inspect host signature/in-place wrapping limits without expanding to heavy framework installation. Root owns build/static/package auditing.\n")'` — exit **0**; [output](artifacts/FRONTEND-log-charter-a-completion.txt).

- **2026-10-03T01:53:25+00:00 → 2026-10-03T01:53:25+00:00** `.venv/bin/python -m ruff check tests/test_qa_adapters.py` — exit **0**; [output](artifacts/FRONTEND-test-lint.txt).

- **2026-10-03T01:53:25+00:00 → 2026-10-03T01:53:25+00:00** `.venv/bin/python -m ruff format --check tests/test_qa_adapters.py` — exit **1**; [output](artifacts/FRONTEND-test-format-check.txt).

- **2026-10-03T01:53:25+00:00 → 2026-10-03T01:53:26+00:00** `.venv/bin/python -m pytest tests/test_qa_adapters.py -q -ra` — exit **0**; [output](artifacts/FRONTEND-adapter-tests-final.txt).

- **2026-10-03T01:53:47+00:00 → 2026-10-03T01:53:47+00:00** `.venv/bin/python -m ruff format tests/test_qa_adapters.py` — exit **0**; [output](artifacts/FRONTEND-format-test.txt).

- **2026-10-03T01:53:47+00:00 → 2026-10-03T01:53:47+00:00** `.venv/bin/python -c 'import asyncio; from unittest.mock import MagicMock; from langchain_core.tools import tool; from sentinel.adapters.langchain import SentinelCallbackHandler; from sentinel.exceptions import ApprovalRejected; calls=[]
@tool
def local_action(value:int)->str:
    """Local QA no-network action."""
    calls.append(value)
    return "executed"
client=MagicMock(); client.create_approval.return_value={"action_id":"qa-action"}; client.wait_for_decision.return_value={"status":"rejected"}; handler=SentinelCallbackHandler(client=client); handler.raise_error=True
for asynchronous in (False,True):
    try:
        value=local_action.ainvoke({"value":7},config={"callbacks":[handler]}) if asynchronous else local_action.invoke({"value":7},config={"callbacks":[handler]})
        if asynchronous: asyncio.run(value)
    except ApprovalRejected: print("propagated rejected decision", "ainvoke" if asynchronous else "invoke")
assert calls==[],calls
assert client.create_approval.call_count==2
print("Tool calls with test-only raise_error override:",calls)'` — exit **0**; [output](artifacts/FRONTEND-suggested-fix-control.txt).

- **2026-10-03T01:53:47+00:00 → 2026-10-03T01:53:47+00:00** `python3 -c 'from pathlib import Path; import datetime; print(datetime.datetime.now(datetime.timezone.utc).isoformat()); p=Path("tests/test_qa_adapters.py"); print("".join(f"{i}: {line}" for i,line in enumerate(p.open(),1))); print(Path("docs/qa/2026-10-02/FRONTEND-LOG.md").read_text())'` — exit **0**; [output](artifacts/FRONTEND-final-evidence-lines.txt).

- **2026-10-03T01:53:47+00:00 → 2026-10-03T01:53:47+00:00** `.venv/bin/python -m ruff check tests/test_qa_adapters.py` — exit **0**; [output](artifacts/FRONTEND-formatted-test-check.txt).

- **2026-10-03T01:53:47+00:00 → 2026-10-03T01:53:48+00:00** `.venv/bin/python -m pytest tests/test_qa_adapters.py -q -ra` — exit **0**; [output](artifacts/FRONTEND-focused-final.txt).

- **2026-10-03T01:54:29+00:00** Timing correction: the earlier FE-A narrative said 9 minutes; command timestamps establish the actual window 01:51:13 to 01:53:25 UTC (2 minutes 12 seconds). The 15-minute figure was the maximum timebox.
- **2026-10-03T01:54:29+00:00** Charter FE-B completed early: focused result 54 passed / 13 strict xfailed; real LangChain 1.6.6 behavior established, test-only raise_error override stopped both invoke/ainvoke after denial. Initial new-test format check failed, formatter applied only to the added test file, final lint passed. Other host framework runtime/version coverage remains unverified.
- **2026-10-03T01:54:29+00:00** Tool edit: apply_patch wrote FRONTEND-REPORT.md containing the substitute justification, scope, FE-001 Critical and FE-002 High, exact reproduction commands, source/test lines, results and limitations. No product code changed.

- **2026-10-03T01:54:29+00:00 → 2026-10-03T01:54:29+00:00** `python3 -c 'from pathlib import Path; from datetime import datetime, timezone; stamp=datetime.now(timezone.utc).isoformat(timespec="seconds"); p=Path("docs/qa/2026-10-02/FRONTEND-LOG.md"); p.open("a").write(f"\n- **{stamp}** Timing correction: the earlier FE-A narrative said 9 minutes; command timestamps establish the actual window 01:51:13 to 01:53:25 UTC (2 minutes 12 seconds). The 15-minute figure was the maximum timebox.\n- **{stamp}** Charter FE-B completed early: focused result 54 passed / 13 strict xfailed; real LangChain 1.6.6 behavior established, test-only raise_error override stopped both invoke/ainvoke after denial. Initial new-test format check failed, formatter applied only to the added test file, final lint passed. Other host framework runtime/version coverage remains unverified.\n- **{stamp}** Tool edit: apply_patch wrote FRONTEND-REPORT.md containing the substitute justification, scope, FE-001 Critical and FE-002 High, exact reproduction commands, source/test lines, results and limitations. No product code changed.\n")'` — exit **0**; [output](artifacts/FRONTEND-report-closeout.txt).

- **2026-10-03T01:54:29+00:00 → 2026-10-03T01:54:29+00:00** `.venv/bin/python -m ruff format --check tests/test_qa_adapters.py` — exit **0**; [output](artifacts/FRONTEND-final-format-check.txt).
