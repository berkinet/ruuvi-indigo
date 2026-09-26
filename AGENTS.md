# Ruuvi Indigo project instructions

- Use zsh for shell commands.
- Work on `main` unless a specific risk or user instruction requires a branch.
- The authoritative public repository is `berkinet/ruuvi-indigo`.
- Inspect the installed Indigo version and an actual decoded HTTP push before
  implementing the transport parser. Do not substitute the `/history` format.
- Use Indigo's existing web server. No additional server, MQTT dependency,
  Gateway polling, action groups, or variables.
- Do not change Tag firmware, disable MQTT, rename existing devices, or migrate
  their consumers during initial development.
- Treat MAC addresses as stable identities. Deduplication and availability are
  independent: every report updates last heard; tag reception timestamps, not
  changing measurement sequences, establish sensor freshness.
- Handle runtime failures at callback and thread boundaries with concise,
  actionable errors. Do not emit Python tracebacks or silently report success
  after failure. Never publish invalid readings as zero.
- Keep real captures, private addresses, credentials, and household dependency
  inventories in ignored `local/`. Public test fixtures must be anonymized.
- When implementation and live verification are complete, update version and
  release notes, run tests and validation, commit and push main, create an
  annotated tag exactly matching PluginVersion (no v prefix), publish a GitHub
  release, and verify the remote commit, tag, and release. Do not release an
  unverified scaffold as an installable plugin.
- Distribution uses Code → Download ZIP, with the plugin bundle at repo root.
