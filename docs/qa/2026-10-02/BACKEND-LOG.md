# Backend QA pass log

All timestamps are UTC. Every shell command is executed through `artifacts/qa_run.py`; its command, timestamps, exit code and sanitized output are recorded in the `BACKEND-*.txt` artifacts and central session log. No production service is contacted.

## 2026-10-03 01:50:53 UTC — Charter BE-A (15-minute timebox)

Explore approval authorization and wait-loop behavior with deterministic local HTTP mocks. Try approved/rejected/unknown decisions, unauthorized responses, legacy `/wait` 404 fallback, expired time budgets, independent clients, and simultaneous calls. The acceptance oracle is fail-closed execution, bounded polling, no implicit retries of approval POSTs, and exact per-client credentials. Read core client, decorator, config, exceptions and existing tests before execution. Checkout verified as `qa/2026-10-02-sweep` at `c302fe8`, remote `PetrefiedThunder/sentinel-sdk`.

Initial inspection: `poll_interval` is unused in both wait loops; every decorator call allocates a client without closing it; exceptions raised by timeout fallback bypass audit emission. These are candidates pending reproduction, not confirmed findings yet.

Tool edit: created this log via `apply_patch`. No product files changed.

Initial command records (the first log header write replaced their generated index entries; original command/output artifacts were retained):

- **2026-10-03T01:50:26+00:00** `pwd` — exit 0; [output](artifacts/BACKEND-initial-identity.txt).
- **2026-10-03T01:50:32+00:00** Python subprocess batch: `git worktree list`, `git status --short --branch`, `git remote get-url origin`, and `rg --files` limited to instruction/project/Python/README files — exit 0; [exact commands and output](artifacts/BACKEND-repo-identity.txt).
- **2026-10-03T01:50:36+00:00** Python numbered source read of project metadata and six core modules — exit 0; [exact command and output](artifacts/BACKEND-core-source.txt).
- **2026-10-03T01:50:41+00:00** Python numbered read of four existing core test modules — exit 0; [exact command and output](artifacts/BACKEND-existing-tests.txt).

- **2026-10-03T01:51:20+00:00 → 2026-10-03T01:51:20+00:00** `python3 -c 'from pathlib import Path; print("venv_ready",Path(".venv/bin/python").exists()); p=Path("tests/conftest.py"); print(p.read_text() if p.exists() else "no tests/conftest.py"); p=Path("docs/qa/2026-10-02/artifacts/qa_run.py"); print(p.read_text())'` — exit **0**; [output](artifacts/BACKEND-harness-and-ready.txt).

- **2026-10-03T01:52:37+00:00 → 2026-10-03T01:52:38+00:00** `.venv/bin/python -m pytest tests/test_qa_backend.py -q -rxX` — exit **1**; [output](artifacts/BACKEND-focused-initial.txt).

- **2026-10-03T01:53:25+00:00 → 2026-10-03T01:53:26+00:00** `.venv/bin/python -m pytest tests/test_qa_backend.py -q -rxX` — exit **0**; [output](artifacts/BACKEND-focused-corrected.txt).

- **2026-10-03T01:53:26+00:00 → 2026-10-03T01:53:26+00:00** `.venv/bin/ruff check tests/test_qa_backend.py` — exit **1**; [output](artifacts/BACKEND-tests-lint.txt).

- **2026-10-03T01:54:09+00:00 → 2026-10-03T01:54:09+00:00** `.venv/bin/ruff format tests/test_qa_backend.py` — exit **0**; [output](artifacts/BACKEND-format-new-tests.txt).

- **2026-10-03T01:54:09+00:00 → 2026-10-03T01:54:10+00:00** `.venv/bin/python -m pytest tests/test_qa_backend.py -q -rxX` — exit **0**; [output](artifacts/BACKEND-focused-final.txt).

- **2026-10-03T01:54:10+00:00 → 2026-10-03T01:54:10+00:00** `.venv/bin/ruff check tests/test_qa_backend.py` — exit **0**; [output](artifacts/BACKEND-tests-lint-final.txt).

- **2026-10-03T01:54:14+00:00 → 2026-10-03T01:54:15+00:00** `.venv/bin/python -m pytest tests/test_qa_backend.py --runxfail -q --tb=short -k 'legacy_wait_paces_pending_requests or late_approval_does_not_bypass_deadline or decorator_closes_client_on_every_exit or timeout_fallback_exception_is_audited or execution_arguments_match_approved_snapshot or config_repr_omits_credential'` — exit **1**; [output](artifacts/BACKEND-negative-controls.txt).

## 2026-10-03 01:54:15 UTC — Charter BE-A result; BE-B starts (10-minute timebox)

BE-A completed early after its deterministic assertions resolved: the intended 15-minute timebox is a maximum, not a delay. Six findings have direct reproductions. Final focused run: **72 passed, 16 strict expected failures**. Hypothesis generated 75 deterministic recursive JSON values. Independent clients and ten simultaneous requests on one async client retained their credentials and idempotency keys. Rejected, missing and unknown decisions, authentication errors, and network failures did not run the protected operation.

Tool edits since the first charter: `apply_patch` added `tests/test_qa_backend.py`, corrected its synchronous mock wrapper, extended JSON/endpoint/concurrency coverage, changed one new-test exception-suppression construct for Ruff, and added the synthetic config-repr regression. `ruff format` touched only that new test file. The initial run's seven failures were test-helper errors (`MagicMock` lacks `__name__`), not product defects; they and the initial lint failure remain in artifacts. The deliberate `--runxfail` negative control failed all 16 expected assertions and no others.

BE-B charter: inspect evidence provenance and map the SDK's local auth, resource, audit and argument-binding risks to OWASP API categories. Verify that each finding has a narrow regression and a practical fix, distinguish server-only unknowns from SDK passes, and write the backend report. No production API, tenant, credential, database, audit ledger or SMS gateway is in scope.

- **2026-10-03T01:54:27+00:00 → 2026-10-03T01:54:27+00:00** `python3 -c 'from pathlib import Path; files=sorted(Path("docs/qa/2026-10-02/artifacts").glob("BACKEND-*.txt")); [(print(p.name),print("\n".join(p.read_text().splitlines()[:3]))) for p in files]'` — exit **0**; [output](artifacts/BACKEND-evidence-index.txt).

- **2026-10-03T01:54:55+00:00 → 2026-10-03T01:54:55+00:00** `rg --files -g '*openapi*' -g '*swagger*' -g '*schema*' -g '*.json' -g '*.yaml' -g '*.yml' -g '!docs/qa/**'` — exit **0**; [output](artifacts/BACKEND-schema-inventory.txt).

- **2026-10-03T01:54:55+00:00 → 2026-10-03T01:54:55+00:00** `python3 -c 'from pathlib import Path; selections={"sentinel/client.py":[(189,221),(368,394)],"sentinel/decorator.py":[(60,107),(111,152)],"sentinel/config.py":[(24,30)]}; [(print("FILE",name),[(print(f"{i}: {lines[i-1]}")) for lo,hi in ranges for i in range(lo,hi+1)]) for name,ranges in selections.items() for lines in [Path(name).read_text().splitlines()]]'` — exit **0**; [output](artifacts/BACKEND-source-line-evidence.txt).

- **2026-10-03T01:56:11+00:00 → 2026-10-03T01:56:11+00:00** `.venv/bin/ruff check tests/test_qa_backend.py` — exit **0**; [output](artifacts/BACKEND-lint-freeze.txt).

- **2026-10-03T01:56:11+00:00 → 2026-10-03T01:56:12+00:00** `.venv/bin/python -m pytest tests/test_qa_backend.py -q -rxX` — exit **0**; [output](artifacts/BACKEND-focused-freeze.txt).

## 2026-10-03T01:56:24+00:00 — BE-B completed; test freeze

Created BACKEND-REPORT.md via apply_patch, recording six findings, the local auth matrix, all ten OWASP category applicability notes, and server-only limits. Strengthened the async polling regression to require an awaited sleep. Final focused rerun: 72 passed, 16 strict xfailed; Ruff passes. No product edits. Both exploratory charters finished before their maximum timeboxes after the written acceptance oracles were resolved. Backend test file is frozen for aggregate root validation.

- **2026-10-03T01:56:24+00:00 → 2026-10-03T01:56:24+00:00** `python3 -c 'from pathlib import Path; from datetime import datetime, timezone; p=Path("docs/qa/2026-10-02/BACKEND-LOG.md"); stamp=datetime.now(timezone.utc).isoformat(timespec="seconds"); p.open("a").write(f"\n## {stamp} — BE-B completed; test freeze\n\nCreated BACKEND-REPORT.md via apply_patch, recording six findings, the local auth matrix, all ten OWASP category applicability notes, and server-only limits. Strengthened the async polling regression to require an awaited sleep. Final focused rerun: 72 passed, 16 strict xfailed; Ruff passes. No product edits. Both exploratory charters finished before their maximum timeboxes after the written acceptance oracles were resolved. Backend test file is frozen for aggregate root validation.\n"); print("Backend report/log completed; test file frozen.")'` — exit **0**; [output](artifacts/BACKEND-close-charter.txt).
