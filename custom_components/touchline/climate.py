"""Platform for Roth Touchline floor heating controller."""

from __future__ import annotations

from typing import Any, NamedTuple

from homeassistant.components.climate import (
    PRESET_AWAY,
    PRESET_NONE,
    PRESET_SLEEP,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, CONF_HOST, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HassTouchline
from .const import _LOGGER, DOMAIN


class PresetMode(NamedTuple):
    """Settings for preset mode."""

    mode: int
    program: int


PRESET_MODES = {
    PRESET_NONE: PresetMode(mode=0, program=0),
    PRESET_SLEEP: PresetMode(mode=1, program=0),
    PRESET_AWAY: PresetMode(mode=2, program=0),
    "program_1": PresetMode(mode=0, program=1),
    "program_2": PresetMode(mode=0, program=2),
    "program_3": PresetMode(mode=0, program=3),
}

TOUCHLINE_HA_PRESETS = {
    (settings.mode, settings.program): preset
    for preset, settings in PRESET_MODES.items()
}


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Touchline device from config entry."""
    host = config.data[CONF_HOST]
    _LOGGER.debug(
        "Host: %s",
        host,
    )

    # Get the PyTouchline instance from hass.data.
    py_touchline = hass.data[DOMAIN][config.entry_id]

    try:
        number_of_devices = await py_touchline.get_number_of_devices_async()
    except Exception as err:
        raise ConfigEntryNotReady(
            f"Error connecting to Touchline controller at {host}"
        ) from err
    _LOGGER.debug(
        "Number of devices found: %s",
        number_of_devices,
    )

    devices = []
    for device_id in range(number_of_devices):
        thermostat = HassTouchline(hass=hass, id=device_id, url=host)
        try:
            await thermostat.update_async()
            devices.append(Touchline(thermostat))
        except Exception as err:
            raise ConfigEntryNotReady(
                f"Error initializing Touchline thermostat {device_id} at {host}"
            ) from err

    _async_migrate_unique_ids(hass, config.entry_id, devices)
    async_add_entities(devices, False)


def _async_migrate_unique_ids(
    hass: HomeAssistant, entry_id: str, devices: list[Touchline]
) -> None:
    """Migrate legacy concatenated thermostat IDs where the mapping is unambiguous."""
    registry = er.async_get(hass)
    legacy_to_new: dict[str, set[str]] = {}
    for device in devices:
        legacy_unique_id = device.legacy_unique_id
        if legacy_unique_id != device.unique_id:
            legacy_to_new.setdefault(legacy_unique_id, set()).add(device.unique_id)

    for legacy_unique_id, new_unique_ids in legacy_to_new.items():
        if len(new_unique_ids) != 1:
            continue
        new_unique_id = new_unique_ids.pop()
        legacy_entity_id = registry.async_get_entity_id(
            "climate", DOMAIN, legacy_unique_id
        )
        legacy_entry = (
            registry.async_get(legacy_entity_id)
            if legacy_entity_id is not None
            else None
        )
        if (
            legacy_entry is not None
            and legacy_entry.config_entry_id == entry_id
            and registry.async_get_entity_id("climate", DOMAIN, new_unique_id) is None
        ):
            registry.async_update_entity(legacy_entity_id, new_unique_id=new_unique_id)


# This class represents the Touchline device.
class Touchline(ClimateEntity):
    """Representation of a Touchline device."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_hvac_mode = HVACMode.HEAT
    _attr_hvac_modes = [HVACMode.HEAT]
    _attr_preset_modes = list(PRESET_MODES)
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_translation_key = "climate"

    def __init__(self, touchline_thermostat: PyTouchline):
        """Initialize the Touchline device."""
        self.unit = touchline_thermostat
        self._device_id = str(self.unit.get_device_id())
        self._controller_id = str(self.unit.get_controller_id())
        if self._device_id == "None" or self._controller_id == "None":
            raise ValueError("Thermostat is missing a device or controller ID")
        self._legacy_unique_id = self._controller_id + self._device_id
        self._attr_unique_id = f"{self._controller_id}_{self._device_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            name=self.unit.get_name(),
            manufacturer="Roth",
        )
        self._attr_native_current_temperature = self.unit.get_current_temperature()
        self._attr_native_target_temperature = self.unit.get_target_temperature()
        self._current_operation_mode = HVACMode.HEAT
        self._attr_preset_mode = self._get_preset_mode()

    @property
    def legacy_unique_id(self) -> str:
        """Return the pre-migration unique ID."""
        return self._legacy_unique_id

    def _get_preset_mode(self) -> str | None:
        return TOUCHLINE_HA_PRESETS.get(
            (self.unit.get_operation_mode(), self.unit.get_week_program())
        )

    async def async_update(self) -> None:
        """Update thermostat attributes."""
        try:
            await self.unit.update_async()
            self._attr_native_current_temperature = self.unit.get_current_temperature()
            self._attr_native_target_temperature = self.unit.get_target_temperature()
            self._attr_preset_mode = self._get_preset_mode()
            self._attr_available = True
        except Exception as err:
            _LOGGER.warning("Update failed for %s: %s", self.name, err)
            self._attr_available = False

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new target preset mode."""
        preset = PRESET_MODES[preset_mode]
        await self.unit.set_operation_mode_async(preset.mode)
        await self.unit.set_week_program_async(preset.program)

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        self._current_operation_mode = HVACMode.HEAT

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            self._attr_native_target_temperature = kwargs.get(ATTR_TEMPERATURE)
        await self.unit.set_target_temperature_async(
            self._attr_native_target_temperature
        )
