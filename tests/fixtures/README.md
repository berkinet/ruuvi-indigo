# Fixture provenance

`decoded-mqtt-anonymized.json` comes from a real Ruuvi Gateway message stored in
an Indigo MQTT connector's last_payload in the saved database, inspected on
September 26, 2026. Gateway and tag MAC addresses were replaced with synthetic
values. The measurements, field names, and timestamps are unchanged.

It is an MQTT fixture, **not an HTTP push fixture**. It must not be used to claim
HTTP compatibility. Add an independently captured and anonymized HTTP push after
inspecting the actual Gateway configuration and firmware.
