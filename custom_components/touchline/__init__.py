"""Platform for Roth Touchline floor heating controller."""

from __future__ import annotations

from typing import override

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import httpx_client
from httpx import AsyncClient
from pytouchline_extended import PyTouchline

from .const import _LOGGER, DOMAIN

PLATFORMS = [Platform.CLIMATE]
_HTTPX_CLIENT = "_httpx_client"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Roth Touchline from a config entry."""

    host = entry.data[CONF_HOST]
    _LOGGER.debug(
        "Host: %s",
        host,
    )

    py_touchline = HassTouchline(hass=hass, url=host)
    try:
        number_of_devices = await py_touchline.get_number_of_devices_async()
    except Exception as err:
        raise ConfigEntryNotReady(
            f"Error connecting to Touchline controller: {err}"
        ) from err

    _LOGGER.debug(
        "Host: %s, Number of devices found: %s",
        host,
        number_of_devices,
    )

    if not number_of_devices:
        raise ConfigEntryNotReady
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = py_touchline
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class HassTouchline(PyTouchline):
    """Use a Home Assistant-managed HTTPX client for Touchline requests."""

    def __init__(
        self, hass: HomeAssistant, id: int = 0, url: str = "", timeout: float = 10.0
    ) -> None:
        """Initialize a Touchline client with Home Assistant's HTTPX client."""
        super().__init__(id=id, url=url, timeout=timeout)
        domain_data = hass.data.setdefault(DOMAIN, {})
        if (async_client := domain_data.get(_HTTPX_CLIENT)) is None:
            async_client = httpx_client.create_async_httpx_client(
                hass, verify_ssl=False, timeout=self._timeout
            )
            domain_data[_HTTPX_CLIENT] = async_client
        self._async_client: AsyncClient = async_client

    @override
    def get_async_client(self) -> AsyncClient:
        """Return the shared Home Assistant-managed client."""
        return self._async_client
