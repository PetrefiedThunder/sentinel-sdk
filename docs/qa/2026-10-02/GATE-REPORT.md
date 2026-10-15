# Independent QA review

PR: opened by orchestrator

CI status: pending at time of writing

## Scope and verdict

Independent local review of the three QA passes, new tests, network-blocking fixture, package/CI configuration, and relevant product code. Worktree and branch were verified before review: `qa/2026-10-02-sweep`, base `c302fe8`. The charter was a maximum 15-minute review focused on false-positive findings, false-green expected failures, test nondeterminism, unintended behavior changes, and missed high-impact approval bypasses. No remote review service, production system, credential file, or environment file was accessed.

**The added tests are suitable for this QA-only change.** No product code change or material defect in the reviewed tests requires correction. This is acceptance of the evidence and tests, not release approval: FE-001 is a verified Critical approval bypass, and the unresolved findings remain expected failures.

## Independent checks

- `tests/test_qa_adapters.py tests/test_qa_backend.py tests/test_qa_dx.py`: **135 passed, 32 xfailed**, zero unexpected failures or skips in the full QA environment. [Transcript](artifacts/GATE-qa-tests.txt).
- Four representative expected failures rerun with `--runxfail`: **4 failed at their intended assertions**. Real LangChain executed the local action after rejection; the mutable payload executed `999` after submission of `10`; a late approval returned after the deadline; and configuration repr contained a synthetic credential marker. [Negative-control transcript](artifacts/GATE-unsuppressed-behaviors.txt).
- Source review confirmed the reported causes in LangChain callback construction, adapter argument selection, polling/deadline logic, decorator lifecycle/audit paths, configuration defaults/repr, and README onboarding. [Client/decorator evidence](artifacts/GATE-source.txt), [adapter evidence](artifacts/GATE-adapter-source.txt), [new-test evidence](artifacts/GATE-inspect.txt).
- All expected failures are strict and name a finding. They restrict expected exception classes; the negative controls demonstrate the current failures occur at the intended assertions. Hypothesis is deterministic (`derandomize=True`, fixed 75 examples, no example database); race reproduction coordinates with asyncio events rather than timing sleeps.
- The network fixture denies socket connection attempts in every test. Added HTTP cases use `httpx.MockTransport`; provider/framework callbacks are mocked except for the local LangChain host itself. No new dependency or product file is changed.

## Severity and overlap review

| Findings | Review |
| --- | --- |
| FE-001 | Critical is justified: the real host executes a rejected operation. Sync, async, timeout, and transport-error variants support one root-cause finding rather than six duplicates. |
| FE-002, BE-004 | High is justified: each can execute inputs that were not the ones reviewed by the human. These are different causes: omitted positional arguments versus mutation during the wait. |
| BE-001, UX-001 | Distinct findings. One ignores request pacing in the wait loop; the other ignores the documented environment setting. A complete polling repair needs both addressed. Cross-reference them. |
| BE-002, BE-003, BE-005 | Medium is appropriate for unclosed decorator-owned clients, missing failure audit evidence on explicit timeout execution, and late decision acceptance. Do not describe local tests as proof of actual resource exhaustion or hosted audit loss. |
| BE-006 | Medium potential secret exposure is appropriate. Only a synthetic marker was used; no real credential exposure was observed. |
| UX-002, UX-003 | Low schematic quickstart gap and Medium premature human approval for an invalid Python call are supported. UX-002 is not an SDK payment-processing defect. |

## Limits that must remain explicit

The standard CI installs only `.[dev]` (see `.github/workflows/ci.yml:23`), so optional LangChain and Hypothesis cases are intentionally skipped there unless those QA extras are installed. They did execute in this local QA environment. Hosted CI has not been queried or run by this reviewer.

Only the installed LangChain version is tested as a real host. Other framework-shaped objects verify wrapper behavior, not every host scheduling/filter/callback contract. Real tenant authorization, server idempotency/replay, provider delivery, cancellation, remote audit persistence, other Python/platform versions, and sustained load are not established by these tests. Browser accessibility and screenshots are not applicable to this SDK.

The reviewer inspected pass reports as available; root QA owns the final mandatory document consistency checks, aggregate coverage, packaging, audit/static results, and secret scan. No new product finding was added during this review.

All commands and their UTC timestamps are recorded in [GATE-LOG.md](GATE-LOG.md).

## Final consolidated-document check

Reviewed all five mandatory documents after assembly. Counts reconcile to **Critical=1 High=2 Medium=7 Low=1**, with six Backend, two adapter and three developer-experience findings. The top-five list and fix order identify the supported highest risks. Python 3.11 **192 passed / 32 xfailed**, dev-only **184 passed / 14 skipped / 26 xfailed**, and Python 3.14 **192 passed / 32 xfailed / 42 warnings** match their saved transcripts. Coverage counters and percentages match all three saved JSON artifacts. Every local link in the five mandatory documents resolves. [Document snapshot](artifacts/GATE-final-documents.txt), [counter/link verification](artifacts/GATE-final-counters.txt).

No consistency discrepancy was found. Documentation explicitly distinguishes local mocks from hosted service proof, current-snapshot from unavailable history scanning, and orchestrator PR ownership from an actual opened PR. No hosted CI or production-readiness claim is made. Root QA retains ownership of the final artifact and secret-scan snapshot after this note.
