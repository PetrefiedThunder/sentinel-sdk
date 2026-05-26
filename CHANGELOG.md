# Changelog

All notable changes to the Sentinel Python SDK (`sentinel-oversight` on PyPI).
This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and adheres to [Semantic Versioning](https://semver.org/).

## [0.1.8] — 2026-05-26

### Fixed
- Fail fast with `TypeError` when `@oversight` arguments contain
  non-JSON-serializable values (sets, bytes, custom objects). Previously
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
