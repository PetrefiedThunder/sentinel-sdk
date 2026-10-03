# Coverage and verification

PR: opened by orchestrator

CI status: pending at time of writing

## Comparable coverage

Coverage.py 7.16.2, Python 3.11.15, `--cov=sentinel --cov-branch`, identical checkout/product source and optional QA dependencies. Baseline explicitly selects the seven original test modules (57 cases); final selects all tests. The offline socket fixture applies to both.

| Run | Passed | Xfailed | Statement coverage | Branch coverage | Combined coverage |
|---|---:|---:|---|---|---|
| Before | 57 | 0 | 384/696 (55.17%) | 75/160 (46.88%) | 53.62% |
| After | 192 | 32 | 665/696 (95.55%) | 137/160 (85.62%) | 93.69% |
| Passing only | 192 | 0 | 656/696 (94.25%) | 132/160 (82.50%) | 92.06% |

The final run includes 32 strict expected failures across 11 findings. Executing a defective path increases coverage but does not establish correct behavior. The separate passing-only run excludes all xfail-marked cases (`-m "not xfail"`, 32 deselected) so that difference is visible. The Hypothesis test checks 75 deterministic recursive JSON examples inside one pytest case.

## Module coverage

Percentages below combine statements and branches. JSON artifacts retain exact counts and missing lines.

| Module | Before | After | Passing only |
|---|---:|---:|---:|
| `sentinel/__init__.py` | 100.00% | 100.00% | 100.00% |
| `sentinel/adapters/anthropic.py` | 0.00% | 90.41% | 90.41% |
| `sentinel/adapters/autogen.py` | 0.00% | 100.00% | 95.00% |
| `sentinel/adapters/crewai.py` | 0.00% | 83.64% | 83.64% |
| `sentinel/adapters/langchain.py` | 0.00% | 87.50% | 87.50% |
| `sentinel/adapters/langgraph.py` | 100.00% | 100.00% | 100.00% |
| `sentinel/adapters/openai_agents.py` | 93.02% | 97.67% | 97.67% |
| `sentinel/adapters/semantic_kernel.py` | 91.18% | 91.18% | 91.18% |
| `sentinel/client.py` | 50.57% | 95.09% | 94.34% |
| `sentinel/config.py` | 92.31% | 92.31% | 92.31% |
| `sentinel/decorator.py` | 69.75% | 91.60% | 83.19% |
| `sentinel/exceptions.py` | 40.74% | 96.30% | 96.30% |

## Executed validation

| Check | Result | Evidence |
|---|---|---|
| Python 3.11 baseline | 57 passed | [Baseline](artifacts/COORD-baseline.txt), [JSON](artifacts/coverage-before.json) |
| Python 3.11 complete QA environment | 192 passed, 32 strict xfailed, no skips | [Final](artifacts/COORD-final-coverage.txt), [JSON](artifacts/coverage-after.json), [JUnit](artifacts/final-junit.xml) |
| Passing-only coverage | 192 passed, 32 deselected | [Run](artifacts/COORD-passing-coverage.txt), [JSON](artifacts/coverage-passing-only.json) |
| Python 3.14.5 | 192 passed, 32 xfailed; 42 deprecation warnings | [Run](artifacts/COORD-final-py314.txt), [JUnit](artifacts/py314-junit.xml) |
| Normal dev extra only, Python 3.11 | 184 passed, 14 skipped, 26 xfailed | [Run](artifacts/COORD-final-dev-only.txt), [JUnit](artifacts/dev-only-junit.xml) |
| Ruff 0.16.8 | Whole-tree lint passed; all five added Python files formatted | [Lint](artifacts/COORD-complete-lint.txt), [Format](artifacts/COORD-changed-format.txt) |
| Advisory mypy 2.4.0 | 25 existing errors across seven adapters | [Output](artifacts/COORD-mypy.txt) |
| Wheel and sdist | Build passed; isolated installed wheel exports/imports passed | [Build](artifacts/COORD-build.txt), [Manifest/hash](artifacts/COORD-wheel-smoke.txt), [Corrected smoke](artifacts/COORD-wheel-smoke-corrected.txt) |
| Installed package consistency | 78 packages compatible in full QA environment | [Check](artifacts/COORD-package-consistency.txt) |
| Public PyPI dependency audit | No known vulnerabilities in 7 runtime / 33 LangChain-extra resolved packages | [Runtime JSON](artifacts/audit-runtime.json), [Extra JSON](artifacts/audit-langchain.json), [Inventory](artifacts/dependency-inventory.json) |
| Independent review | 135 passed, 32 xfailed for new tests; selected unmasked failures verified | [Report](GATE-REPORT.md) |

The 14 normal-dev skips are 13 optional LangChain cases and one optional Hypothesis property test. Six skipped LangChain cases are otherwise xfailed; seven otherwise pass. Existing CI installs only `[dev]`, so the Critical host-integration regression is **not exercised by that configuration**. Both extras were installed and exercised locally. This sweep changes no CI configuration.

## Remaining untested areas

- Hosted API authorization, cross-tenant object ownership, actual idempotency replay/deduplication, notification/consent delivery, billing, audit persistence/hash-chain correctness and live API schema compatibility. No server or checked-in OpenAPI/schema is present.

- Actual frameworks other than langchain-core 1.6.6; LangChain lower-bound/version matrix; provider/model calls, streaming, cancellation and framework scheduling. Other adapters use their real wrappers with plain functions or host-shaped local stubs.

- Python 3.12/3.13, Linux/Windows, real HTTP/TLS and load/resource exhaustion. Cooperative async request isolation is tested; threaded lazy client initialization races are not.

- Some serializer truncation/repr and tuple/list branches, malformed configuration fallback, successful timeout-fallback audit paths, adapter invalid-object/unsupported-kernel branches, and several optional query/no-op close branches remain uncovered. Exact misses appear in the final coverage output.

- Browser/a11y/responsive/performance screenshots are inapplicable to this SDK. Linked websites were never contacted. Text artifacts document the developer journey.

- Full Git history secret scanning could not run on this read-only partial clone. Current snapshot scan cannot prove historical secret absence.


Dependency audit results cover the exact currently resolved runtime and advertised LangChain extra, not all versions permitted by open-ended lower bounds or the QA toolchain. The complete QA tool inventory is in [COORD-environment.txt](artifacts/COORD-environment.txt).

Final handoff checks: [document/count/link validation](artifacts/COORD-validate-handoff.txt), [unchanged product scope](artifacts/COORD-tracked-scope.txt), [redacted current-snapshot secret scan](artifacts/COORD-final-secret-scan.txt), [sanitized scan summary](artifacts/secret-scan-summary.json). Independent final document consistency review passed in [GATE-REPORT.md](GATE-REPORT.md).
