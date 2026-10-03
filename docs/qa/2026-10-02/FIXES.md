# QA fix pass — 2026-10-02

Local branch: `qa/2026-10-02-fixes`. Starting commit: `ede988f9774aeed0eea1eb81dbe46795698a964c`.

Work order: FE-001 (Critical), FE-002 (High), BE-004 (High), following the original SUMMARY recommendation. BE-004 is deferred because a complete safe fix needs an explicit public input/identity contract. Optional work follows these decisions.

| Finding ID | Severity | Title | Status | Commit SHA | Proving test (file::name) | Notes or reason deferred |
|---|---|---|---|---|---|---|
| FE-001 | Critical | LangChain executes tools after gate failure | fixed | ca17f70 | `tests/test_qa_adapters.py::test_real_langchain_tool_does_not_run_after_gate_failure`; `tests/test_qa_adapters.py::test_real_langchain_http_gate_failures_block_execution` | Enable callback error propagation. Rejection, timeout, network errors, malformed JSON/body types, and non-2xx responses block real sync/async tools. 36 host cases pass on LangChain 1.6.6 and lower bound 0.3.0. Explicit decorator timeout fallback remains documented. |
| FE-002 | High | Mixed calls omit positional execution inputs from approval | fixed | b1a9a1d | `tests/test_qa_adapters.py::test_mixed_sync_arguments_are_fully_presented_for_approval`; `tests/test_qa_adapters.py::test_mixed_async_arguments_are_fully_presented_for_approval`; `tests/test_adapter_arguments.py::test_omitted_nonserializable_default_stays_out_of_approval` | Bind all supplied mixed arguments; preserve both argument sets when signature inspection is unavailable. Preserve existing nonmixed payloads and omitted defaults. 190 related tests passed. Independent review caught and corrected an omitted-default compatibility regression before commit. |
| BE-004 | High | Mutable inputs differ from the approved payload | deferred | — | `tests/test_qa_backend.py::test_execution_arguments_match_approved_snapshot` (strict xfail retained) | Deep-copying arbitrary objects can redirect method/self side effects or break caller-visible mutations; custom copy methods can return original references. Rejecting unsupported objects breaks currently accepted calls. Needs a supported-input snapshot and method/object-identity decision. Digest comparison alone leaves a check/use race. Original negative control still fails with 999 executed versus 10 approved. |
| BE-003 | Medium | Failed timeout fallback lacks an execution audit | fixed | c94bea6 | `tests/test_qa_backend.py::test_timeout_fallback_exception_is_audited`; `tests/test_qa_backend.py::test_timeout_fallback_success_is_audited` | Audit failed explicit fallback in sync/async mode, retaining timeout reason and the original exception. Exactly one execution and one audit attempt. Delivery remains best effort. |
| UX-003 | Medium | Incomplete calls request approval before reporting a caller error | fixed | d470fa9 | `tests/test_qa_dx.py::test_missing_required_argument_fails_before_requesting_human_approval`; `tests/test_qa_backend.py::test_missing_arguments_never_request_approval` | Full signature binding rejects missing positional/keyword-only arguments before sync/async approval requests. Five failing pre-fix cases now pass. |

FixCounts: fixed=2 partial=0 deferred=1

## Counts

Counts cover all Critical/High findings and the two optional Medium findings changed in this pass. Other optional findings were not selected.

| Severity | Fixed | Partial | Deferred |
|---|---:|---:|---:|
| Critical | 1 | 0 | 0 |
| High | 1 | 0 | 1 |
| Medium (touched) | 2 | 0 | 0 |
| Low (touched) | 0 | 0 | 0 |
| Total included | 4 | 0 | 1 |

Critical/High only: **2 fixed, 0 partial, 1 deferred**. No fix required a revert. The FE-002 omitted-default issue was caught and corrected before its commit.

## Full-suite comparison

| Run | Passed | Failed/errors | Xfailed | Skipped |
|---|---:|---:|---:|---:|
| Sweep final Python 3.11 baseline (COVERAGE.md) | 192 | 0 | 32 | 0 |
| Fix-pass baseline, rerun before product edits | 192 | 0 | 32 | 0 |
| Fix-pass final Python 3.11.15 | 319 | 0 | 16 | 0 |
| Sweep Python 3.14.5 baseline | 192 | 0 | 32 | 0 |
| Fix-pass final Python 3.14.5 | 319 | 0 | 16 | 0 |

Sixteen strict expected failures became ordinary passing cases; 111 additional regression/control cases were added. All 16 remaining expected failures correspond to untouched findings: BE-001 (2), BE-002 (8), BE-004 (1), BE-005 (2), BE-006 (1), UX-001 (1), UX-002 (1). No unexpected failures or optional skips in the full QA environment.

Evidence: [rerun baseline](artifacts/FIX-SESSION-baseline.txt), [final full suite](artifacts/FIX-SESSION-final-suite.txt), [Python 3.14](artifacts/FIX-SESSION-final-py314.txt), [JUnit/coverage counters](artifacts/FIX-SESSION-final-coverage-summary.txt). The final suite ran after product commit `d470fa9` with the pinned QA extras installed. Test sockets were blocked; approval-service responses were mocked.

Combined coverage: **93.69% sweep → 94.56% final**. Final statement coverage: 695/721 (96.39%); branch coverage: 140/162 (86.42%). Coverage includes expected-failure execution and does not imply unresolved findings are fixed. Python 3.14 emits 108 warnings from the existing `asyncio.iscoroutinefunction` deprecation paths (42 during the smaller sweep suite); no deprecation refactor was made.

## Build, lint, typecheck and review

| Check | Before (sweep) | After |
|---|---|---|
| Wheel and sdist build | Passed | Passed, `uv build --out-dir /private/tmp/sentinel-fix-dist` |
| Isolated installed-wheel smoke | Passed | Passed; imports, version and packaged mixed-argument helper verified |
| Whole-tree Ruff lint | Passed | Passed, `.venv/bin/ruff check .` |
| Ruff formatting | Added QA files passed | All 11 changed Python files passed |
| Advisory mypy | 25 errors in 7 adapter modules | Same 25 diagnostics in the same 7 modules; compared by path, message and count, ignoring shifted line numbers |
| Independent local review | QA test review passed | All four fixes passed; FE-002 review issue corrected before commit |
| Real LangChain host gates | 6 strict expected failures on 1.6.6 | 36 passing host cases on 1.6.6 and 0.3.0 |

Evidence: [build](artifacts/FIX-SESSION-final-build.txt), [wheel smoke](artifacts/FIX-SESSION-installed-wheel-smoke.txt), [lint](artifacts/FIX-SESSION-final-lint.txt), [format](artifacts/FIX-SESSION-final-format.txt), [mypy](artifacts/FIX-SESSION-final-types.txt), [baseline comparison](artifacts/FIX-SESSION-type-baseline-compare.txt), [LangChain 0.3.0](artifacts/FIX-SESSION-fe001-langchain03-corrected.txt). Advisory type failures were pre-existing and were recorded, not repaired. The [redacted full-fix diff scan](artifacts/FIX-SESSION-full-fix-secret-scan.txt) found no leaks across 891362 bytes; this is local diff evidence, not a full-history scan.

No manifests, lockfiles, migrations, deployment configuration, CI configuration, environment files, credentials or secret-scan baselines/ignores were changed. Package downloads were only for an isolated lower-bound LangChain test and installed-wheel verification. No production requests, remote Git mutations, pushes, PR operations or deployments occurred. Builds, installed test packages, caches, JUnit and coverage output remain outside the committed fix artifacts.

## Remaining risks and deferred work

- **BE-004 remains High and unresolved.** Caller-owned mutable arguments can change after approval. A complete fix requires a decision on supported snapshot inputs, method/object identity and caller-visible mutations. Copying only JSON containers or comparing a digest would not close the full gap. The existing failing test stays strict xfail.
- Untouched Medium findings remain: legacy polling pacing (BE-001), late-decision deadline handling (BE-005), ignored interval configuration (UX-001), decorator-owned client cleanup (BE-002), and credential-bearing diagnostic repr (BE-006). The polling/deadline/configuration and resource-lifecycle changes were not selected for this small optional pass. Credential handling was outside the authorized fix scope. The Low quickstart example issue (UX-002) remains unchanged.
- FE-001 propagates gate failures; the separate BE-005 late-decision defect is still present. Explicit `@oversight(fallback="execute")` or configured timeout execution remains opt-in and documented. Audit delivery is best effort; this pass proves an audit attempt, not durable server evidence.
- Ordinary CI installs only `[dev]` and can skip optional LangChain host tests. The complete QA environment ran them locally; CI configuration was not changed. Framework versions between the tested endpoints, real non-LangChain hosts, streaming, cancellation and production approval flows remain unverified.
- Hosted CI, production authorization/tenant isolation, notifications, durable audit persistence, full Git-history scanning, and publication are not validated by these local tests. The SDK is not cleared for a safety-sensitive release while the High snapshot finding remains open.

See [FIX-SESSION-LOG.md](FIX-SESSION-LOG.md) for UTC commands, outcomes, negative controls, review corrections and dead ends.
