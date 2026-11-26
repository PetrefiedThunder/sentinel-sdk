# Pass 3: UX QA — developer experience

This repository ships a Python SDK, with no webpage, graphical client, or CLI. The useful UX surface is installation, the README quickstart, configuration, exceptions, callable metadata, and recovery from invalid input. WCAG 2.2 AA/axe, screen-reader and keyboard checks, mobile/responsive layouts, graphical empty/loading/error states, Lighthouse, cross-browser checks, and screenshots are **not applicable**. No synthetic interface was created to manufacture visual evidence. Command transcripts are the appropriate artifacts.

## Method and scope

Two exploratory charters, each with a 15-minute ceiling, are timestamped in [UX-LOG.md](UX-LOG.md). They prioritize the first integration and predictable failure behavior. Documentation-derived tests execute the actual first Python fence from README.md, stub SentinelClient and the payment symbol, and exercise environment settings independently. This is a low-level test-pyramid approach: deterministic local examples and boundary tests provide stronger evidence here than a browser workflow. Existing product source and documentation were not changed.

The README payment example is schematic. UX-002 is an onboarding documentation gap, **not a claim that the SDK itself cannot transfer funds**. With the missing external symbol supplied as a stub, the example passes and prevents execution on rejection. The SMS prerequisites and hosted-service behavior are documented but were not verified against a server.

## Findings

| ID | Severity | Group | Title | Exact reproduction | Expected versus actual | Evidence | Suggested fix |
| --- | --- | --- | --- | --- | --- | --- | --- |
| UX-001 | Medium | UX / developer experience | Documented poll-interval environment variable is ignored | Run `.venv/bin/python3.11 -m pytest tests/test_qa_dx.py --runxfail -q -k readme_environment_configuration`. The parameter case clears Sentinel environment values, sets `SENTINEL_POLL_INTERVAL=0.25`, and constructs `SentinelConfig()`. | Expected `poll_interval == 0.25` per the README configuration table; actual `2.0`. Other four documented configuration variables pass their isolated cases. | `README.md:157`; `sentinel/config.py:29`; `tests/test_qa_dx.py:106`; [negative-control transcript](artifacts/UX-ux-negative-controls.txt). | Read and validate `SENTINEL_POLL_INTERVAL` through a default factory; coordinate with the backend polling fix so the accepted setting also affects fallback request pacing. |
| UX-002 | Low | UX / developer experience | Quickstart has no self-contained executable example | Run `.venv/bin/python3.11 -m pytest tests/test_qa_dx.py --runxfail -q -k test_readme_quickstart_runs_after_approval`. The test executes the first README Python fence with configure/approval mocked, then calls `transfer_funds(1000, "acct_qa")`. | Expected a newcomer to be able to complete a safe first approval using the presented setup; actual function execution raises `NameError: name 'stripe' is not defined`. The excerpt omits the external library import/setup and the only first-call example has payment side effects. | `README.md:29`; `README.md:40`; `tests/test_qa_dx.py:50`; [negative-control transcript](artifacts/UX-ux-negative-controls.txt). The positive stubbed-payment test passes. | Provide a safe, self-contained first example returning a value or printing a message. Label the payment example schematic, list its prerequisites, and link SMS consent requirements before the first run. |
| UX-003 | Medium | UX / developer experience | Missing required arguments request human approval before reporting the caller error | Run `.venv/bin/python3.11 -m pytest tests/test_qa_dx.py --runxfail -q -k test_missing_required_argument_fails_before_requesting_human_approval`. With an approved mocked response, call the README's decorated `transfer_funds(1000)` without `recipient`. | Expected `TypeError` before creating an approval, as for a normal Python function; actual approval creation receives only `{"amount": 1000}`, waits for a decision, then raises `TypeError`. This can waste a human approval and delay a deterministic caller error. | `sentinel/decorator.py:37`; `sentinel/decorator.py:117`; `sentinel/decorator.py:142`; `tests/test_qa_dx.py:147`; [negative-control transcript](artifacts/UX-ux-negative-controls.txt). | Use full `signature.bind` before creating the approval; cover both synchronous and asynchronous wrappers through the shared binding helper. |

## Adapted Nielsen 10-heuristic review

| Heuristic | SDK review and result |
| --- | --- |
| Visibility of system status | Blocking approval and timeout behavior are explained at `README.md:43-50`. Local rejection exposes reason and action ID. Live delivery/progress visibility cannot be established in this repository. |
| Match between system and real world | Function name and bound arguments are readable in approval requests; the tested payment example preserves `amount` and `recipient`. No payment operation was performed. |
| User control and freedom | Rejection prevents payment execution in the offline quickstart test. Fallback execution is explicitly mentioned at `README.md:50` and in the configuration table; actual backend approvals are outside this pass. |
| Consistency and standards | `configure`, `SentinelClient`, exported exception types, and standard Python decorator metadata are discoverable. UX-001 identifies a concrete inconsistency between the documented environment interface and behavior. |
| Error prevention | Missing configuration fails before HTTP client construction, with a `sentinel.configure(api_key=...)` recovery instruction. UX-003 identifies an avoidable approval request for an invalid Python call. |
| Recognition rather than recall | README lists approver formats, exception classes, and environment settings. The documented `SentinelConfig`/`configure` API can be explored through Python metadata without a graphical interface. |
| Flexibility and efficiency of use | Decorator retains the wrapped callable name, docstring, and signature. Partial `configure` updates preserve other fields. Global configuration and explicit client configuration coexist; no live tenant switching was attempted. |
| Aesthetic and minimalist design | The document uses one installation command and sectioned code examples. UX-002 records the unnecessary external payment prerequisites in the first runnable path. |
| Help users recognize, diagnose, recover from errors | Missing-key recovery and human-rejection reason/action ID pass. Product/API error and transport behavior are assessed separately by Backend QA. |
| Help and documentation | `CONTRIBUTING.md:8-14` gives editable installation and pytest instructions; root QA owns package/build/static-tool validation. Hosted account setup, notification routing, signed links, consent enforcement, and audit-chain claims are explicitly unverified locally. |

## Verification

- Latest targeted test run: **9 passed, 3 xfailed**, exit 0, [transcript](artifacts/UX-ux-invalid-argument-test.txt).
- Expected failures are strict and limited to the relevant exception class. Running the same file with `--runxfail` proves **3 failed, 9 passed**, each for its recorded finding, [transcript](artifacts/UX-ux-negative-controls.txt).
- Ruff lint: passed, [transcript](artifacts/UX-ux-test-lint.txt).
- Ruff formatting check: passed, [transcript](artifacts/UX-ux-test-format.txt).
- Consolidated before/after coverage belongs to [COVERAGE.md](COVERAGE.md); this pass adds 12 deterministic cases without adding dependencies.

## Limits

No production URL, account signup, notification provider, payment provider, backend API, database, billing service, environment file, or credential file was accessed. Public documentation hyperlinks were inspected as text only. Synthetic values are test fixtures. No real credentials were observed in the files reviewed. There is no local OpenAPI document proving hosted behaviors in the README, and no UI to capture. The asynchronous missing-required-argument path was inspected through its shared helper but was not separately executed in this pass.

PR: opened by orchestrator

CI status: pending at time of writing
