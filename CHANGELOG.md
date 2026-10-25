# Changelog

All notable changes to the Sentinel Python SDK (`sentinel-oversight` on PyPI).
This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed (breaking)
- `@oversight` now fails fast on arguments that are not JSON-serializable.
  Any argument (at any nesting depth) that is not `str`, `int`, `float`,
  `bool`, `None`, `list`, `tuple` or `dict` raises `TypeError` before any
  approval request is sent. The message names the offending argument path
  and type, e.g. `arguments['payload']['tags'] is of type set`. Previously
  the decorator silently replaced such values with their `repr()`, so
  approvers saw a string that did not match what the function received.
  This matches the direct client (`SentinelClient.create_approval`) and the
  `crewai` / `autogen` adapters, which already raised `TypeError`.
  - `@oversight` also rejects dict keys that are not `str`. Previously
    `{1: "a"}` was sent as `{"1": "a"}`, `{True: "a"}` as `{"True": "a"}`,
    and `{1: "a", "1": "b"}` collapsed to one key, so the approver could
    see a different dict than the function received.
  - Migration: convert values before calling the decorated function. Sets
    to lists (`sorted(s)` or `list(s)`), bytes to base64 strings
    (`base64.b64encode(b).decode()`), custom objects to dicts
    (`dataclasses.asdict(obj)`, `obj.model_dump()`, or a hand-built dict),
    non-str dict keys to `str`.
- `NaN`, `Infinity` and `-Infinity` float arguments now raise `TypeError`
  from `@oversight`, the direct client and the adapters. They are not valid
  JSON; httpx previously raised `ValueError` while encoding the request.

### Deprecated
- The `@oversight` repr-conversion behavior of `sentinel-oversight` 0.1.x
  on PyPI (including 0.1.8 and 0.1.9) is removed in 0.2.0. The 0.1.8
  `TypeError` check below ran only in the direct client; `@oversight` had
  already repr-converted sets, bytes and custom objects into strings before
  that check, so decorator calls never hit it. Code that relied on this
  conversion must convert those values itself before upgrading to 0.2.0,
  or the call will raise `TypeError`.

### Fixed
- Exception audits from an approved `@oversight` call are no longer dropped.
  The API requires `execution_result` to be a string and rejects JSON null.
  Audit posts are best-effort and do not raise, so that 422 left no execution
  record when the wrapped function raised. A missing result is now sent as
  `failed` when `error` is set, and as an empty string otherwise. The
  exception text stays in `error`.

## [0.2.0]

### Changed (breaking)
- `@oversight` now fails fast on arguments that are not JSON-serializable.
  Any argument (at any nesting depth) that is not `str`, `int`, `float`,
  `bool`, `None`, `list`, `tuple` or `dict` raises `TypeError` before any
  approval request is sent. The message names the offending argument path
  and type, e.g. `arguments['payload']['tags'] is of type set`. Previously
  the decorator silently replaced such values with their `repr()`, so
  approvers saw a string that did not match what the function received.
  This matches the direct client (`SentinelClient.create_approval`) and the
  `crewai` / `autogen` adapters, which already raised `TypeError`.
  - `@oversight`, the direct client and both adapters reject dict keys that
    are not `str`. Previously
    `{1: "a"}` was sent as `{"1": "a"}`, `{True: "a"}` as `{"True": "a"}`,
    and `{1: "a", "1": "b"}` collapsed to one key, so the approver could
    see a different dict than the function received.
  - Migration: convert values before calling the decorated function. Sets
    to lists (`sorted(s)` or `list(s)`), bytes to base64 strings
    (`base64.b64encode(b).decode()`), custom objects to dicts
    (`dataclasses.asdict(obj)`, `obj.model_dump()`, or a hand-built dict),
    non-str dict keys to `str`.
- `NaN`, `Infinity` and `-Infinity` float arguments now raise `TypeError`
  from `@oversight`, the direct client and the adapters. They are not valid
  JSON; httpx previously raised `ValueError` while encoding the request.

### Deprecated
- The `@oversight` repr-conversion behavior of `sentinel-oversight` 0.1.x
  on PyPI (including 0.1.8 and 0.1.9) is removed in 0.2.0. The 0.1.8
  `TypeError` check below ran only in the direct client; `@oversight` had
  already repr-converted sets, bytes and custom objects into strings before
  that check, so decorator calls never hit it. Code that relied on this
  conversion must convert those values itself before upgrading to 0.2.0,
  or the call will raise `TypeError`.

## [0.1.9] — 2026-05-26

### Added
- `sentinel.adapters.crewai.gated(tool, ...)` — wrap any CrewAI tool
  (BaseTool instance or `@tool`-decorated callable) so each invocation
  pauses for Sentinel approval. Preserves the tool's external interface
  so CrewAI's executor calls it normally.
- `sentinel.adapters.autogen.gated(...)` — decorator for AutoGen-style
  tool functions. Detects sync vs. async automatically, preserves
  `functools.wraps` metadata so AutoGen's tool registration sees the
  original signature.

## [0.1.8] — 2026-05-26

### Fixed
- Fail fast with `TypeError` when `SentinelClient.create_approval`
  arguments contain non-JSON-serializable values (sets, bytes, custom
  objects). `@oversight` was not affected: it still repr-converted such
  values to strings before this check, until 0.2.0. Previously
  the call silently succeeded at the SDK layer, then hung for the full
  `timeout_seconds` waiting on an approval the decorator could never
  surface. The validation runs client-side via `json.dumps`, so the
  caller sees the real error immediately.

## [0.1.7] — 2026-05-25

### Added
- `SentinelClient.get_tenant()` — fetch current tenant settings.
- `SentinelClient.set_default_approvers([...])` — configure
  workspace-level fallback approvers used when a decorator omits
  `approvers=[...]`. Async equivalents shipped too.
- README section "Default approvers" documenting the 4-step
  resolution order: caller → tenant defaults → env-var → 400.

## [0.1.6] — 2026-05-25

### Added
- SMS consent lifecycle: `register_sms_contact`,
  `list_sms_contacts`, `revoke_sms_contact`. Required before any
  `sms:+1...` approver is accepted by the API. TCPA-compliant.

## [0.1.5] — 2026-05-25

### Changed
- Default `api_url` is now `https://api.pauseapi.app` (edge-terminated
  via Vercel proxy → Railway origin). Drops typical RTT by 100–200ms.

## [0.1.0–0.1.4]

Initial public releases: `@oversight` decorator, magic-link approve /
reject via signed HMAC tokens, hash-chained audit log, Postgres
LISTEN/NOTIFY for sub-100ms decision detection.
