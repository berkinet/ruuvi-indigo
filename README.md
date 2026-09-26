# Ruuvi Gateway for Indigo

An Indigo plugin in development to receive decoded Ruuvi Gateway HTTP pushes
through Indigo's existing web server and expose one native sensor device per
RuuviTag. Target installation: Indigo 2025.2.0.

**Status: discovery and repository setup. No installable plugin or release yet.**
A real decoded MQTT message has been inspected, but the Gateway's actual decoded
HTTP push and installed firmware have not yet been inspected. The MQTT sample is
not evidence for the HTTP envelope. Implementation must follow that inspection.

## Scope

- Stable device identity from the sensor MAC address; preserve user device names.
- Native numeric sensor states, with explicit units and missing-value handling.
- Measurement sequence deduplication, including rollover and sensor restarts.
- Separate report receipt, sensor reception, and measurement timestamps.
- Stale-sensor detection independent of measurement changes.
- No MQTT dependency, network polling, additional server, action groups, or variables.
- Keep the existing MQTT Shims devices and Tag firmware unchanged during development.

See [design and verification](docs/design.md), [migration](docs/migration.md),
and [official references](docs/references.md).

## Repository and eventual distribution

The authoritative repository is `berkinet/ruuvi-indigo`, using `main` and the
same `year.major.minor` release convention as `berkinet/phidgets22-indigo`.
Once verified, the plugin bundle will live at the repository root. Install via
GitHub **Code → Download ZIP**, extract, and open the `.indigoPlugin` bundle.
Version tags will match `PluginVersion` exactly, without a `v` prefix. No custom
ZIP release assets are needed.

Local captures, configuration, credentials, and migration inventories belong in
the ignored `local/` directory. Public fixtures must be anonymized and identify
their source and transport explicitly.
