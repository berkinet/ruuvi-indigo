# Fixture provenance

`decoded-mqtt-anonymized.json` comes from a real Ruuvi Gateway message stored in
an Indigo MQTT connector's last_payload in the saved database, inspected on
September 26, 2026. Gateway and tag MAC addresses were replaced with synthetic
values. The measurements, field names, and timestamps are unchanged.

It is an MQTT fixture, **not an HTTP push fixture**. It is used to ensure the
HTTP parser rejects the distinct MQTT shape.

`decoded-http-anonymized.json` is an independent real HTTP push captured through
Indigo's existing web server on September 26, 2026, after configuring Gateway
v1.16.3 to send decoded JSON every 30 seconds with Bearer authentication. It has
two RAWv2 tags. Only MAC addresses were replaced; measurements and timestamps
are unchanged. No credentials or request headers are included.
