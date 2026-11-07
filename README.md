
# Custom Home Assistant component for Roth Touchline

This component overrides the bundled [touchline][1] component in Home Assistant.

### Configuration and compatibility

Configure the integration through Home Assistant's UI. YAML configuration is no longer
supported; remove any `touchline` section from `configuration.yaml` and add the
controller through **Settings → Devices & services → Add integration**.

This custom integration uses the asynchronous API in `pytouchline_extended`. The bundled
integration also supports UI configuration, so UI setup is not a difference between the
two integrations.

Thermostat entity IDs use stable controller and device identifiers. Existing entity
registry entries are migrated automatically when their old IDs map to one thermostat
without ambiguity. Preset names follow Home Assistant conventions; update automations
and scripts using the old names:

| Previous preset | New preset |
| --- | --- |
| `Normal` | `none` |
| `Night` | `sleep` |
| `Holiday` | `away` |
| `Pro 1` | `program_1` |
| `Pro 2` | `program_2` |
| `Pro 3` | `program_3` |

[1]: https://www.home-assistant.io/integrations/touchline
