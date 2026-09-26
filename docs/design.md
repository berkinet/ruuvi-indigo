# Design and verification

## Observations

The installed Indigo client and server Info.plist files both report 2025.2.0.
The existing MQTT Shims decoder imports Df5Decoder and decodes raw advertising
data. A separate saved MQTT connector payload is already decoded; its anonymized
copy is in `tests/fixtures/decoded-mqtt-anonymized.json`. This is a saved database
snapshot, not a new HTTP capture or proof of current sensor health.

That payload contains `dataFormat: 5`, temperature in degrees Celsius, humidity
in percent, pressure in Pa, acceleration in g, voltage in V, transmit power and
RSSI in dBm, movement counter, measurementSequenceNumber, sensor ID, Gateway MAC,
Gateway reporting time (`gwts`), and sensor reception time (`ts`).

The published HTTP push envelope instead contains `data.tags` keyed by sensor
MAC, `data.timestamp` for reporting time, and a per-tag `timestamp` for reception
time. Its example documents raw advertising data. Do not construct a supposedly
real decoded HTTP fixture by wrapping the MQTT sample in this envelope.

## HTTP integration

Use `/message/com.berkinet.indigoplugin.ruuvi/receive/` on Indigo's existing web
server. Indigo requires a hidden plugin action declaration for this callback;
this is internal routing, not a user action group. The documented callback
receives `incoming_request_method`, `headers`, and `request_body` in action.props.

Indigo documents Bearer API-key authentication, and Ruuvi documents Bearer support.
Verify this pairing against the installed web server configuration and Gateway
firmware without changing global web-server security. Never log authorization
headers or commit credentials. Verify unauthenticated requests are rejected
before sensor state changes.

Indigo accepts a response dictionary containing integer `status`, optional
`headers`, and string `content`. Check the actual Gateway's accepted success
status, timeout, and retry behavior before selecting the response contract.
Validate the full request before creating devices. Bound request size and tag
count. Reject malformed requests clearly; isolate malformed readings without
substituting zero, and never acknowledge an update that failed as successful.

The Webhooks API also offers JSON POST processing and broadcasts to subscribing
plugins, but the documented setup uses a Web Server trigger. The direct plugin
callback gives this plugin its own request validation and HTTP response without
requiring a user trigger or action script.

The supplied Gateway is reachable: its root page returned HTTP 200 and a
`Server: Ruuvi Gateway` header. Reading `/ruuvi.json` returned a redirect to
`/#auth`; authentication is required before its configuration and firmware can
be inspected. Its address is retained only in local working context.

## Sensor identity and states

Normalize valid MAC addresses to uppercase colon-separated form. Reuse an existing
device belonging to this plugin with that address; never duplicate it on restart
or rename it on receipt. Do not take over existing MQTT Shims devices.

Use Indigo's native sensorValue for temperature and numeric device states for
humidity, pressure, voltage, acceleration, movement, RSSI, and measurement sequence.
Expose measurement availability separately. Use Celsius initially to match the
existing devices. If pressure is displayed in hPa, convert Pa by dividing by 100;
do not apply raw Bluetooth scaling to values already decoded by the Gateway.
Battery voltage is not a battery percentage.

Handle omitted/null/non-finite/unavailable readings without publishing false
zeroes. Keep the last valid numeric value with an explicit unavailable indicator
and visible status. Validate decoded ranges and integer counters. RAWv2 sequence
65535 and movement counter 255 mean unavailable, not valid counter values.

## Independent freshness and deduplication

- `lastHeard`: Indigo receipt time, updated on every valid report for this tag,
  including duplicate measurements.
- `gatewayReportedAt`: Gateway batch report time.
- `sensorReceivedAt`: most recent actual tag reception time reported by Gateway.
- `lastMeasurementAt`: time associated with the last accepted new measurement.

An equal valid measurement sequence suppresses redundant measurement updates,
not reception metadata or availability updates. A newer tag reception timestamp
with unchanged measurements keeps a sensor healthy. A cached tag record with an
old reception timestamp must eventually become stale despite fresh batch reports.

Use reception-time ordering to prevent delayed batches overwriting newer data.
Do not require sequence values to increase: rollover and restarts can lower them.
Consider same-sequence collisions after a long outage/restart; persist enough
state to avoid accidental replay or permanent suppression across plugin restarts.
Missing sequence disables sequence deduplication rather than dropping the report.

Track local elapsed time with a monotonic clock where possible, and handle
Gateway clock skew/reset explicitly. If timestamps are absent, surface that
freshness is based on report receipt with reduced confidence. A local stale-time
check may run periodically; it performs no network polling. Threshold must be
configurable and comfortably exceed the Gateway push interval.

## Required verification before replacement

1. Inspect Gateway firmware, HTTP settings, and real decoded HTTP push.
2. Confirm endpoint authentication and Gateway success/retry response behavior.
3. Test actual fixture, invalid JSON, unexpected shape, empty batches, missing
   readings, malformed MACs, unsupported formats, units, and non-finite numbers.
4. Test equal sequence/new reception, equal sequence/cached reception, rollover,
   restart, delayed reports, missing sequence, and clock changes.
5. Verify one device per MAC, restart persistence, and preservation of names.
6. Test stale transitions and recovery with simulated time, independently of
   measurement changes; confirm behavior in Indigo with the real Gateway.
7. Compare replacement readings alongside MQTT Shims without disabling it.
8. Inventory and migrate consumers only after the replacement is verified.
