# Design and verification

## Observed versions and wire format

The installed Indigo client/server are 2025.2.0, API 3.8, Python 3.13.9. The
Gateway runs v1.16.3 with radio firmware v2.0.0. These were inspected before
implementing the receiver, along with an actual decoded HTTP push captured by
Indigo's existing web server. The anonymized capture is
`tests/fixtures/decoded-http-anonymized.json`.

The HTTP envelope contains `data.tags` keyed by sensor MAC, `data.timestamp`
for the Gateway report, and `timestamp` inside each tag for radio reception.
It differs from both MQTT and `/history`. The separate MQTT fixture verifies
that the HTTP parser rejects the MQTT shape. Decoded RAWv2 temperature is °C,
humidity %, pressure Pa, acceleration g, and battery voltage V. Only pressure
is rescaled, to hPa. Battery voltage is not converted to a percentage.

## Transport

Indigo routes `/message/com.berkinet.indigoplugin.ruuvi/receive/` to a hidden
plugin action. This is internal callback routing, with no user action group,
trigger, action script, or variable. The callback receives
`incoming_request_method`, `headers`, and `request_body` in `action.props`.
Indigo authenticates the request before invoking the plugin.

The user entered an Indigo API key directly into the Gateway's Bearer field.
The Gateway's Check succeeded, and a subsequent real two-tag push reached the
endpoint. An unauthenticated HTTP POST returned 401 before and after deployment.
The plugin never reads or logs authorization headers. Credentials and private
captures are excluded from the repository.

The installed IWS implementation requires an `indigo.Dict` response with integer
`status`, an optional header dictionary, and **nonempty** string `content`.
An empty content value takes IWS's error path. The receiver returns 200 with a
small JSON summary. Gateway v1.16.3 source accepts 200–299; non-success changes
its HTTP retry period to 67 seconds. No rate override header is sent, so the
configured Gateway sending interval remains authoritative. This source review
does not establish that delivery timing is reliable in the live installation.

The parser validates the entire envelope before changing devices, with a
256 KiB body limit and at most 256 tags. Invalid JSON/envelopes return 400;
unsupported formats are counted as ignored. Unavailable individual readings
retain the prior numeric value with an explicit availability flag of false.
A runtime state-write failure returns 500; already-applied measurements are
safe to retry. Logs contain concise errors, not payloads or tracebacks.

## Stable identities and state

MAC addresses are normalized to uppercase colon-separated form and used as
Indigo device addresses. Discovery reuses matching devices owned by this plugin,
preserves user-assigned names, and does not take over MQTT Shims devices. A
configured duplicate MAC is reported as an error. Disabled devices are skipped.

The native `sensorValue` is temperature. Other readings have numeric states
and individual Boolean availability states. Missing temperature sets a native
sensor error. Temperature keeps RAWv2's three decimal places internally with a
two-decimal display. Persistent `tracking` contains deduplication and freshness
bookkeeping; no Indigo variables are used.

## Independent deduplication and freshness

An equal valid sequence and equal decoded measurements suppress redundant
measurement writes. A smaller sequence with current reception timing is valid,
including rollover and Tag restarts. Reused sequences with changed values are
accepted. Missing/unavailable sequence numbers disable deduplication.

`lastHeard` records each valid tag report's arrival at Indigo, including
duplicates and discarded older receptions. `gatewayReportedAt` and
`sensorReceivedAt` expose accepted source timestamps separately.
`lastMeasurementAt` records acceptance of new measurements.

A newer radio reception refreshes availability even for an unchanged sequence.
A repeated cached reception does not. Empty batches never refresh sensors.
Older receptions cannot overwrite newer readings. The five-second local
freshness check performs no network access. Stale devices retain their readings
but set `stale=true` and a native sensor error; fresh receptions clear the error.

Local elapsed time uses a monotonic clock anchored at startup. A future-skewed
Gateway clock uses report-to-reception age and does not refresh repeated source
timestamps. Its correction to current time starts a new reception epoch.
Past-skewed clocks and delayed old reports cannot be distinguished and are
conservatively treated as old. Without a sensor timestamp, freshness falls back
to report receipt and `timeQuality=reportReceipt`; this cannot identify cached
radio data. Keep NTP enabled. Tracking survives plugin restarts, but a host
clock change across restarts can temporarily mark sensors stale until fresh
source timestamps arrive.

## Verification status

See [verification](verification.md) for automated and live evidence and any
outstanding delivery issue. MQTT remains the production integration until
sustained HTTP delivery and the explicit consumer migration are verified.
