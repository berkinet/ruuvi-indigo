# Migration without disrupting MQTT Shims

Leave the MQTT connector, decoder, Shims devices, Gateway MQTT configuration,
and Tag firmware unchanged. Initial HTTP development runs alongside them.

The saved database contains devices named **Ruuvitag Freezer** and
**Ruuvitag Refrigerator**. Their IDs and MAC addresses are recorded privately in
`local/migration-inventory.md` and the local payload capture. The saved snapshot
may not match live configuration.

Keep the existing device names during development. New plugin devices need
distinct temporary names while both integrations coexist. Preserve any name the
user assigns to a replacement; discovery must not overwrite it.

Before cutover, enumerate live trigger device references and state names, action
conditions, scripts, control pages, logging, and integrations consuming either
existing device. The initial saved-XML scan found no exact device-ID references
inside Trigger, ActionGroup, Schedule, or other Device elements, but this does
not rule out embedded scripts, encoded references, or external consumers.

Native sensorValue temperature consumers may be straightforward to move, but
the replacement has a different device ID. Update each reference explicitly;
renaming a device does not redirect consumers. Map other states individually,
checking units and unavailable-state conditions.

After sustained side-by-side verification, retain the familiar names on the
replacement devices through a coordinated rename and reference migration. Keep
a rollback inventory and the original devices until cutover is confirmed. No
such migration or MQTT shutdown has been performed by this project.
