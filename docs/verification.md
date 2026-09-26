# Verification record — 2026-09-26

## Automated

35 standard-library unittest cases cover the real anonymized HTTP fixture,
rejection of the MQTT shape, malformed/oversized requests, duplicate MACs,
whole-envelope validation, unavailable values and RAWv2 sentinels, unit
conversion, empty batches, unsupported formats, equal sequences with fresh
versus cached reception, rollover/restart/reused sequences, missing sequences,
out-of-order reports, clock skew/correction, delayed first reports, stale
recovery, persistent tracking, discovery, preserved names, disabled devices,
Gateway restrictions, state-write failure/retry, and Indigo callback responses.
The Indigo boundary tests use a stateful fake bridge, including XML state names.

## Live evidence

- Inspected Indigo 2025.2.0/API 3.8/Python 3.13.9 and Gateway v1.16.3/radio v2.0.0.
- Gateway Bearer-authenticated Check succeeded; captured an independent decoded
  HTTP push with two real tags before implementing the parser.
- Unauthenticated POST rejected with 401, including after deployment.
- Replaying the real payload through Indigo created exactly two native sensors.
- A later genuine Gateway push updated both devices with current values.
- After five minutes without a newer HTTP reception, both devices became stale
  automatically. MQTT Shims continued to update, confirming the integrations
  remain independent.
- A subsequent genuine push cleared both stale errors and restored full-precision
  readings.
- Restarting the Ruuvi plugin reused the same two devices and preserved names
  and tracking. Replaying the exact current readings with their original source
  timestamps returned two duplicates and zero measurements before and after
  restart, without refreshing reception freshness.
- A response-only packet capture confirmed HTTP 200, a nonempty JSON summary,
  and a matching Content-Length. No authorization headers were captured.
- Existing MQTT device names, IDs, control-page references, Gateway MQTT
  configuration, and Tag firmware were left unchanged.

## Gateway delivery and remaining observation

Before a Gateway restart, custom HTTP delivery was intermittent despite saved
30-second settings, while MQTT continued. Both native sensors correctly became
stale and recovered on the next real push. The receiver logged no callback
errors. The saved URL, decoded format, interval, and Bearer mode were rechecked.

The user power-cycled the Gateway once. HTTP delivery then resumed at the
configured 30-second interval with successful 200 responses. A bounded capture
recorded four consecutive successes at 16:18:56, 16:19:26, 16:19:56, and
16:20:26 UTC; both devices were still Online on the following report. MQTT also resumed
and reported Connected. Contemporaneous HTTP/MQTT temperature readings agreed
closely, with different radio reception times; this is not a claim that their
independently scheduled reports are identical samples.

The underlying cause of the pre-restart forwarding gap was not established.
This is session-level verification, not a long-duration reliability test. Keep
MQTT Shims active during continued observation and before migrating consumers.
No MQTT shutdown, Tag firmware change, or consumer migration has occurred.
