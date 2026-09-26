# Migration without disrupting MQTT Shims

Leave the MQTT connector, decoder, Shims devices, Gateway MQTT configuration,
and Tag firmware unchanged. Initial HTTP development runs alongside them.

The existing device IDs, names, MAC addresses, and control-page consumers are
recorded privately in `local/migration-inventory.md`. Live API reads confirmed
the saved identities and current MQTT readings. The two new native devices use
the corresponding original names with ` (HTTP)` appended during verification.

Keep the existing device names during development. New plugin devices need
distinct temporary names while both integrations coexist. Preserve any name the
user assigns to a replacement; discovery must not overwrite it.

Before cutover, enumerate live trigger device references and state names, action
conditions, scripts, control pages, logging, and integrations consuming either
existing device. The initial saved-XML scan found no exact device-ID references
inside Trigger, ActionGroup, Schedule, or other Device elements, but this does
not rule out embedded scripts, encoded references, or external consumers.
Inspection of the active database under the Databases directory subsequently
found references to both devices on two control pages; their names and IDs are
recorded in the private inventory. These control-page references must also be
repointed at cutover. No matching trigger device-ID references were found in
that file; review name-based scripts and live trigger configuration separately.

Native sensorValue temperature consumers may be straightforward to move, but
the replacement has a different device ID. Update each reference explicitly;
renaming a device does not redirect consumers. Map other states individually,
checking units and unavailable-state conditions.

After sustained side-by-side verification, retain the familiar names on the
replacement devices through a coordinated rename and reference migration. Keep
a rollback inventory and the original devices until cutover is confirmed. No
such migration or MQTT shutdown has been performed by this project.
