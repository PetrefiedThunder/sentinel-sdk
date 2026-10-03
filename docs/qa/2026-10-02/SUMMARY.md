# QA sweep summary — 2026-10-02

PR: opened by orchestrator

CI status: pending at time of writing

Counts: Critical=1 High=2 Medium=7 Low=1

**The QA evidence is ready for orchestrator review. The SDK has an unresolved Critical approval-enforcement defect and is not cleared for a safety-sensitive release.** All changes are uncommitted on `qa/2026-10-02-sweep`, starting at `c302fe8`. No product code, deployment configuration, environment files, migrations or CI controls were changed. No product one-line fixes were applied.

The orchestrator owns the commit, push and single draft PR. “PR: opened by orchestrator” is the required ownership placeholder; this session did not open a PR and has no PR URL or hosted CI result. Local checks below are not hosted CI or production proof.

## Findings by group

| Group | Critical | High | Medium | Low | Total |
|---|---:|---:|---:|---:|---:|
| Backend: client, decorator, configuration | 0 | 1 | 5 | 0 | 6 |
| Frontend substitute: adapter integration | 1 | 1 | 0 | 0 | 2 |
| UX substitute: developer experience | 0 | 0 | 2 | 1 | 3 |
| Total | 1 | 2 | 7 | 1 | 11 |

This Python SDK has no UI. Browser, screenshot, WCAG, screen-reader, responsive-layout and Lighthouse checks were replaced with adapter/package and developer-experience testing, as planned. No visual results are claimed for the linked websites.

## Top five risks in plain language

1. **FE-001 — Critical:** LangChain runs a protected tool even when the approval is rejected, times out, or fails to connect. Proven with real local `invoke` and `ainvoke` calls on langchain-core 1.6.6.
2. **FE-002 — High:** Four adapters can ask a human to approve only part of a function's inputs, then execute all of them. A positional amount disappears when a keyword recipient is supplied.
3. **BE-004 — High:** A second task can change a shared input while approval is pending; the function then executes a different amount from the one submitted for approval. This requires shared mutable state in the same process.
4. **BE-001 — Medium:** Legacy-server polling ignores its configured interval and immediately repeats requests, risking unnecessary API load while an approval is pending. No production load test was performed.
5. **BE-006 — Medium:** Printing/logging a configuration object includes its API credential. The proof uses a synthetic value; no actual secret was found or exposed.

All 11 findings have exact reproductions, expected/actual behavior, code references and suggested fixes in [FINDINGS.md](FINDINGS.md).

## Verification outcomes

- **Baseline:** 57 passed. **Final Python 3.11:** 192 passed, 32 strict expected failures, no skips. Added tests contain 135 passing cases and 32 expected failures; no existing test was weakened. Deterministic property testing adds 75 JSON examples inside one case.
- **Coverage:** statement coverage 55.17% → 95.55%; branch coverage 46.88% → 85.62%; combined 53.62% → 93.69%. Excluding all known-defect tests gives 92.06% combined coverage. Execution coverage is not a claim those defects are fixed.
- **Compatibility:** Python 3.14.5 also reports 192 passed / 32 xfailed, with 42 existing `asyncio.iscoroutinefunction` deprecation warnings. Normal `[dev]`-only installation reports 184 passed / 26 xfailed / 14 optional skips. The six Critical LangChain regression cases are among those normal-CI skips; the full QA environment executed them.
- **Static checks:** whole-tree Ruff lint and formatting of added Python files pass. Advisory mypy reports 25 existing errors across seven adapters; type checking is not an existing CI gate.
- **Packaging:** wheel and sdist build passed; isolated installed-wheel import/export/version checks passed, including the optional LangChain installation message. An initial eager-import assumption in the QA smoke was wrong; the corrected lazy-instantiation check passed and both transcripts are retained.
- **Dependency audit:** public PyPI metadata reports no known vulnerabilities for the exact 7-package runtime and 33-package LangChain-extra closures. This is neither a guarantee for all allowed versions nor an audit of every QA-tool dependency.
- **Secrets:** current-snapshot redacted scan passed. Git-history scanning was unavailable: a read-only partial clone blocked an implicit promisor fetch, and the scanner processed zero commits despite exit 0. No historical-secret safety claim is made. Final snapshot handoff evidence is recorded in the coordination log.
- **Independent review:** verified test intent, real host fail-open behavior, severity, xfail scope and absence of product changes. Selected regressions failed at their intended assertions when xfail handling was disabled.

The initial test-helper failures, initial new-file lint/format failures, corrected wheel-smoke assumption, failed history scan, and intentional unmasked regressions are all retained in the [session log](SESSION-LOG.md) and linked pass artifacts. See [COVERAGE.md](COVERAGE.md) for exact counters, matrix and artifact links.

## Recommended next-fix order

1. **FE-001:** propagate LangChain callback failures, retain real-host negative tests, and add optional-framework coverage to the normal verification workflow.
2. **FE-002, BE-004:** bind every callable input to approval and establish safe snapshot semantics for mutable arguments.
3. **BE-001, BE-005, UX-001:** fix polling pacing and deadline enforcement, then wire up the documented environment interval.
4. **BE-006, BE-002, BE-003:** omit credentials from diagnostic repr, close decorator-owned clients on every exit, and audit exceptions during explicit timeout fallback execution.
5. **UX-003, UX-002:** reject incomplete calls before requesting human approval and provide a safe self-contained onboarding example.

These are suggested product changes for follow-up work, not changes made by this QA sweep.

## What could not be tested

- Production and real third-party services were prohibited. Server auth/roles, cross-tenant access, actual replay deduplication, SMS/email delivery, consent enforcement, durable audit chains, credentials and billing remain unverified.
- No checked-in OpenAPI/schema exists; captured request contracts verify SDK expectations and sync/async parity only.
- Real host integration is limited to LangChain 1.6.6. Other framework adapters use local functions and host-shaped stubs. Older supported framework versions, streaming/provider calls and host cancellation remain unverified.
- Python 3.12/3.13, Linux/Windows, real TLS/network timing, descriptor exhaustion, long-running load and threaded lazy-initialization races were outside this focused local sweep.
- Browser and accessibility checks/screenshots do not apply to this repository. No linked production webpage was visited.
- Full Git-history secret scanning, hosted CI, remote PR status and publication are unavailable in this session and remain orchestrator work.

## Handoff contents

The five mandatory documents, three separate QA pass logs/reports, independent review, pinned optional QA-tool requirements, sanitized command runner, command outputs, coverage JSON, JUnit reports and dependency audit JSON are under `docs/qa/2026-10-02/`. Four new test/configuration files are under `tests/`. Build distributions and temporary isolated environments remain under `/private/tmp`; their manifests/results are saved as text evidence. No screenshots are needed for the SDK-only surface.

Final handoff checks: [document/count/link validation](artifacts/COORD-validate-handoff.txt), [unchanged product scope](artifacts/COORD-tracked-scope.txt), [redacted current-snapshot secret scan](artifacts/COORD-final-secret-scan.txt), [sanitized scan summary](artifacts/secret-scan-summary.json). Independent final document consistency review passed in [GATE-REPORT.md](GATE-REPORT.md).
