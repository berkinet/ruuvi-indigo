# Changelog

## 2026.1.1 — 2026-09-27

- Continue processing healthy sensors after individual device creation, state, or
  health-update failures, while retaining HTTP 500 for incomplete batches.
- Isolate invalid configured MACs and block duplicate identities without creating
  extra devices or starving unrelated sensors.
- Log actionable configuration diagnostics with device IDs while withholding
  private addresses and arbitrary bridge exception text.
- Return the validated Gateway identity from the parser, avoiding a second JSON
  decode and preserving empty-batch Gateway restrictions.
- Add eight regression tests (43 total) for isolation, retry, diagnostics, and
  normalized empty-batch identity.

Live verification confirmed both existing sensors receiving new Gateway pushes
on 2026.1.1, preserved IDs/names, callback handling of old/empty/malformed batches,
and continued HTTP authentication enforcement.

## 2026.1.0 — 2026-09-26

- Receive authenticated decoded RAWv2 HTTP pushes through Indigo's web server.
- Create one native sensor per MAC with numeric readings and availability flags.
- Separate sequence deduplication from reception freshness and stale detection.
- Persist tracking across restarts; handle rollover, restarts, unavailable values,
  delayed reports, unit conversion, and clock uncertainty.
- Validate bounded batches and return explicit HTTP results without logging secrets.
- Add 35 tests and an anonymized real HTTP capture.
- Preserve MQTT Shims and document consumer migration.

Live verification covered authenticated pushes, HTTP 200 responses, stale and
recovery transitions, and duplicate suppression after plugin restart. A
user-performed Gateway power restart restored its configured 30-second HTTP
cadence after initial intermittent delivery. MQTT remains active; no consumer
migration has been performed.
