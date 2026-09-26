# Ruuvi Gateway for Indigo

Receive decoded Ruuvi Gateway HTTP pushes through Indigo's existing web server.
Each RuuviTag becomes one native Indigo temperature sensor with numeric states
for its other measurements. No MQTT dependency, Gateway polling, additional
server, action groups, or variables.

**Version 2026.1.0.** Verified with authenticated live pushes, stale/recovery
transitions, and plugin restart persistence. Keep MQTT Shims in service during
your own side-by-side observation; see the [verification record](docs/verification.md).

Requires **Indigo 2025.2 / API 3.8 / Python 3.13**. Developed against a real
Gateway running **v1.16.3**, radio firmware **v2.0.0**, and decoded RAWv2
(data format 5) pushes. Other Ruuvi data formats are ignored.

## Installation

1. On [GitHub](https://github.com/berkinet/ruuvi-indigo), choose **Code → Download ZIP**.
2. Extract and open **Ruuvi Gateway.indigoPlugin**. Select Install and Enable.
3. Set the plugin's stale timeout (default: 300 seconds). Optionally restrict
   reports to your Gateway's Bluetooth MAC, as reported in `gw_mac`; this can
   differ from its Wi-Fi MAC.
4. Configure the Gateway below. Sensors are created automatically by MAC.
   You may rename them; subsequent reports preserve the names.

The stable plugin ID is **`com.berkinet.indigoplugin.ruuvi`**.

## Gateway configuration

In Custom Server settings, enable HTTP(S) and use:

```text
http://INDIGO_LAN_ADDRESS:8176/message/com.berkinet.indigoplugin.ruuvi/receive/
```

Use your actual Indigo web-server port and scheme. Select **Send only decoded
data**, a **30-second** sending interval, **Use authentication**, and **Bearer
authentication**. Enter an Indigo API key or configured local secret without
the word `Bearer`. Never include the key in a shared screenshot or repository.
The local HTTP connection is unencrypted; use an already-configured HTTPS
endpoint when transport encryption is required.

Use **Check**, then finish the wizard. The check can send an empty tag batch;
normal batches arrive after setup finishes. Indigo must reject unauthenticated
requests. Do not disable web-server authentication.

Keep MQTT enabled during side-by-side verification. The Gateway may briefly
pause forwarding while its wizard is open and resumes when the wizard finishes.
This plugin never changes Gateway or Tag firmware.

## Device states

| State | Meaning / units |
| --- | --- |
| `sensorValue`, `temperature` | Temperature, °C; `sensorValue` is Indigo's native sensor value |
| `humidity` | Relative humidity, % |
| `pressure` | hPa (converted from the Gateway's Pa) |
| `voltage` | Battery voltage, V; not a battery percentage |
| `accelX`, `accelY`, `accelZ` | Acceleration, g |
| `movementCounter` | RAWv2 movement counter |
| `txPower`, `rssi` | dBm |
| `measurementSequenceNumber` | Measurement sequence, 0–65534 |
| `stale`, `status` | Freshness and visible health |
| `lastHeard` | Indigo receipt of every valid tag report, including duplicates |
| `gatewayReportedAt` | Gateway batch-report timestamp |
| `sensorReceivedAt` | Gateway's last radio reception timestamp for this tag |
| `lastMeasurementAt` | Indigo acceptance time of the last new measurement |
| `duplicateCount`, `outOfOrderCount` | Duplicate measurements and discarded older reports |
| `timeQuality` | `sensorTimestamp`, `gatewayRelative`, `reportReceipt`, or `clockUncertain` |
| `lastReportKind` | `measurement`, `duplicate`, or `outOfOrder` |
| `missingReadings` | Fields unavailable in the last accepted measurement |

Each measurement and RSSI also has an `Available` Boolean, for example
`humidityAvailable`. Missing, null, non-finite, and unavailable values retain
the last valid number with availability false; they never become false zeroes.
Missing temperature puts the native sensor into an error state. Consumers must
check availability and `stale` before using retained values. `tracking` is
plugin bookkeeping stored on the device for restart persistence.

## Duplicates and stale sensors

An unchanged valid sequence and unchanged measurements count as a duplicate.
Reception metadata still updates. A newer reception with unchanged measurements
keeps a sensor online; repeating an old cached reception does not. A decreased
sequence is accepted with current reception timing, supporting rollover and Tag
restarts. Changed values with a reused sequence are accepted. An unavailable
sequence disables deduplication for that report.

Freshness is checked locally every five seconds, with no network polling.
Default stale threshold: five minutes. A fresh reception clears stale status
even if measurements did not change. Deduplication survives plugin restarts.

Older reception timestamps cannot replace newer readings. Timestamp-less
reports use report-receipt freshness (`timeQuality=reportReceipt`); this cannot
distinguish cached reports from new receptions. A future-skewed Gateway clock
uses relative report/reception age, but repeating a timestamp does not refresh
freshness. Past-skewed clocks and delayed old reports are handled conservatively
as stale because they cannot be distinguished. Correcting a future-skewed clock
to current time is supported. Keep Gateway NTP enabled.

## HTTP responses

- **200**: applied batch with `measurements`, `duplicates`, `outOfOrder`, and
  `ignored` counts. Empty batches do not touch sensor freshness.
- **400**: malformed envelope, mismatched identities, or raw-only reports.
- **401**: Indigo web-server authentication rejected the request.
- **403**: Gateway MAC does not match the configured restriction.
- **405**: callback requires POST.
- **413**: request exceeds 256 KiB.
- **500**: batch could not be fully applied; retry is safe. Already-applied
  updates are deduplicated on retry.

The full envelope is validated before devices are created. At most 256 tags
are accepted. Unknown formats count as ignored. Payloads and credentials are
not logged.

## Migration and development

Keep existing MQTT Shims devices and names until verification is complete.
Replacement devices have different Indigo IDs; consumers must be repointed
explicitly. See [migration](docs/migration.md), [design](docs/design.md), and
[official references](docs/references.md).

Run tests with Python 3.13:

```zsh
python3.13 -m unittest discover -s tests -v
```

Repository conventions match `berkinet/phidgets22-indigo`: main branch, MIT
license, year.major.minor versions, annotated tags matching PluginVersion
without a v prefix, and GitHub releases. Distribution uses **Code → Download
ZIP**, not custom ZIP assets. Private captures and inventories stay in ignored
`local/`; public fixtures are anonymized.
