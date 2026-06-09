
# Custom Home Assistant component for Roth Touchline

This component overrides the bundled [touchline][1] component in Home Assistant.

### Why this is better than the bundled integration
- **Modern Configuration:** Supports Home Assistant's UI-based configuration (Config Flow), eliminating the need to edit `configuration.yaml` manually.
- **Asynchronous Execution:** Built using `asyncio`, ensuring that it doesn't block the Home Assistant main thread during network operations, leading to better overall performance and stability.
- **Enhanced Library:** Uses `pytouchline_extended`, providing improved communication with Roth Touchline devices.
- **Seamless Override:** Automatically takes precedence over the built-in integration while maintaining the same `touchline` domain.

[1]: https://www.home-assistant.io/integrations/touchline
