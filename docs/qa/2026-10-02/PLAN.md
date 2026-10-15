# QA sweep plan — 2026-10-02

PR: opened by orchestrator

CI status: pending at time of writing

## Scope and checkout

- Repository: `PetrefiedThunder/sentinel-sdk`; checkout `/Users/sellers/Projects/qa-sweep-2026-10-02/sentinel-sdk`.
- Starting commit: `c302fe8`; working branch: `qa/2026-10-02-sweep`. Initial tree was clean; one worktree.
- Python package `sentinel-oversight` 0.1.9, Python >=3.11, HTTPX transport. There is no server, database, web UI, browser app, or checked-in OpenAPI/schema.
- 36 tracked files. Core: `sentinel/client.py` (HTTP, polling, pagination, consent and audit), `config.py`, `decorator.py`, `exceptions.py`. Integration boundary: seven framework adapters under `sentinel/adapters/`. Seven existing test modules use mocks. `README.md`, `CONTRIBUTING.md`, packaging and workflow configuration describe the developer journey.
- Read-only instruction discovery found no repository/directory AGENTS.md. `/Users/sellers/AGENTS.md` contains stale RegEngine paths/deployment descriptions; they are irrelevant here. The supplied task and orchestrator constraints govern this checkout.

## Risk ranking

Scores are planning estimates: impact and likelihood each 1–5, multiplied. They are not measured incident probabilities.

| Rank | Area | Impact | Likelihood | Score | Reason |
|---|---|---:|---:|---:|---|
| 1 | Approval enforcement across decorator/adapters | 5 | 4 | 20 | A rejected or malformed decision must not execute the protected action; callback frameworks may suppress errors. |
| 2 | Timeout, polling, retry and resource lifecycle | 4 | 4 | 16 | Approval can wait minutes; loops and per-call clients affect reliability under repeated/concurrent use. |
| 3 | Audit and argument fidelity | 5 | 3 | 15 | Approvers must see the action actually executed; success/error evidence must describe it correctly. |
| 4 | Authentication and independent client configuration | 5 | 2 | 10 | Credentials must be present before transport and remain scoped to the intended client. Server tenant enforcement is unavailable. |
| 5 | Public API, framework contracts and installation | 3 | 3 | 9 | Import/install/type/signature failures prevent integration; mocks alone miss host behavior. |
| 6 | README onboarding and error recovery | 3 | 3 | 9 | Configuration claims and examples determine whether developers use the SDK safely. |
| 7 | Dependency vulnerabilities and static hygiene | 4 | 2 | 8 | A small runtime dependency tree still needs a package/advisory review. |

## Three independent passes

Each pass has its own owner, timestamped log, written exploratory charters and report. Passes can execute concurrently on disjoint test/report files. Coordination owns aggregate baseline/final checks to avoid coverage-data collisions.

1. **Backend QA** ([log](BACKEND-LOG.md)): unit/transport integration tests with `httpx.MockTransport`; sync/async authorization and decision matrices; boundary/equivalence cases; deterministic property cases where useful; idempotency header/409 behavior, concurrency, timeout and audit failure exploration. A local OWASP API Top 10 applicability review distinguishes client checks from unverified server controls. Use an initial 15-minute transport/decision charter and a 15-minute lifecycle/error charter, extending only to reproduce material defects.
2. **Frontend QA → adapter integration and packaging** ([log](FRONTEND-LOG.md)): no frontend exists. Substitute local host-boundary tests across adapters, real installed LangChain callback behavior where feasible, wheel/sdist build and isolated wheel import smoke, Ruff and advisory type checking. This is the closest equivalent of component and end-to-end integration QA for an SDK. Use 15-minute enforcement and 15-minute packaging/contract charters. Chromium/Firefox/WebKit, Lighthouse, console/network UI checks and screenshots are inapplicable to this repository.
3. **UX QA → developer experience** ([log](UX-LOG.md)): execute documented examples using local stubs, compare documented config/errors with implementation, review discoverability, defaults, recovery, async/public API ergonomics, and adapt Nielsen's ten heuristics to SDK use. Use 15-minute onboarding and 15-minute config/error charters. There is no renderable product UI, so WCAG/axe, manual keyboard/screen reader, responsive layout and visual state screenshots are inapplicable. Text transcripts and test evidence replace screenshots; this is not an accessibility certification of linked websites.

## Methods and evidence

- Test pyramid: many deterministic unit/negative-path cases, fewer real HTTPX mock-transport and framework integrations, then build/install smoke. No live service tests.
- Existing suites run with statement and branch coverage before additions and again afterward using the same environment. Coverage of expected failures is explicitly distinguished from passing behavior.
- Add tests only, keeping defects as strict expected failures with finding IDs and narrow expected failure types. Do not weaken existing tests. No product fix is planned.
- Ruff uses the declared pinned version; mypy is an advisory check because no baseline type-check configuration exists. Build artifacts and dependency versions are recorded. QA-only tools are isolated from runtime dependencies.
- Audit installed runtime/advertised-extra dependencies using public PyPI package metadata; do not query authenticated services. Package freshness is separate from vulnerability status. If the network rule/tool prevents advisory lookup, report it as unverified.
- All test HTTP is mocked and synthetic. A test fixture blocks socket network use. The command logger strips inherited credential variables, uses an isolated HOME, redacts credential-shaped output, and records each command with UTC timestamps, exit and artifact links.
- Findings require a concrete repro or test and exact code/document reference, expected/actual behavior, severity and suggested fix. Potential issues without sufficient evidence remain limitations, not confirmed bugs.
- Independent final local review verifies test quality, findings, scope, mandatory docs, expected failures, whitespace/lint, and redacted secret scan before handoff.

## Boundaries and completion

No production URLs, databases, credentials, environment files, billing, remote deployment/migration commands, repository pushes, commits or PR commands. No product code, CI secret-scanning rules, deployment settings or migration edits. Existing workflow files may be read to understand current checks only. No external CodeRabbit review: it uploads source and exceeds this task's network scope.

The orchestrator owns secret review, commit, push and the single draft PR. This working session ends with uncommitted tests and all five mandatory QA documents, three pass logs/reports, reproducible artifacts, local results and explicit limitations. The PR wording above records ownership, not evidence that a PR already exists. Hosted CI and the PR URL remain unavailable until the orchestrator publishes.
