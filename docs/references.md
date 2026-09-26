# Official references

- [Ruuvi HTTP push configuration](https://docs.ruuvi.com/ruuvi-gateway-firmware/gateway-html-pages/cloud-options/backend-http-s): decoded JSON, authentication, and sending interval.
- [Ruuvi payload formats](https://docs.ruuvi.com/ruuvi-gateway-firmware/data-formats): select HTTP push; do not assume it matches `/history`.
- [HTTP time-stamped push](https://docs.ruuvi.com/ruuvi-gateway-firmware/data-formats/http-time-stamped-data-from-bluetooth-sensors): Gateway report timestamp and per-tag reception timestamp. The published raw-data example is not a captured decoded push.
- [Indigo plugin developer guide](https://docs.indigodomo.com/2025.2/plugin-dev/guide/): plugin layout and distribution.
- [Indigo HTTP callback reference](https://docs.indigodomo.com/2025.2/plugin-dev/reference/plugin-py/http-requests/): receiving requests through the existing web server, authentication, callback properties, and response structure.
- [Ruuvi RAWv2 definitions](https://docs.ruuvi.com/communication/bluetooth-advertisements/data-format-5-rawv2): sequence numbers, units, unavailable values, and test vectors.

Checked September 26, 2026. Verify the installed Gateway's firmware behavior
against its actual push before finalizing the parser or response contract.
