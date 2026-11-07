"""Tests for Roth Touchline climate platform."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.touchline.climate import Touchline, async_setup_entry
from custom_components.touchline.const import DOMAIN


@pytest.fixture
def mock_config_entry(hass: HomeAssistant):
    """Mock a config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "http://127.0.0.2"},
        entry_id="test_entry_id",
    )
    entry.add_to_hass(hass)
    return entry


def make_thermostat(device_id=1, controller_id=42):
    """Create a thermostat with representative library values."""
    thermostat = MagicMock()
    thermostat.get_name.return_value = f"Room {device_id}"
    thermostat.get_device_id.return_value = device_id
    thermostat.get_controller_id.return_value = controller_id
    thermostat.get_current_temperature.return_value = 21.0
    thermostat.get_target_temperature.return_value = 22.0
    thermostat.get_operation_mode.return_value = 0
    thermostat.get_week_program.return_value = 0
    thermostat.update_async = AsyncMock()
    thermostat.set_operation_mode_async = AsyncMock()
    thermostat.set_week_program_async = AsyncMock()
    thermostat.set_target_temperature_async = AsyncMock()
    return thermostat


@patch("custom_components.touchline.climate.HassTouchline")
async def test_climate_setup_entry(mock_py_touchline, hass, mock_config_entry):
    """Thermostats are initialized and have stable IDs before being added."""
    controller = MagicMock()
    controller.get_number_of_devices_async = AsyncMock(return_value=2)
    hass.data[DOMAIN] = {mock_config_entry.entry_id: controller}
    thermostats = [make_thermostat(1), make_thermostat(2)]
    mock_py_touchline.side_effect = thermostats
    async_add_entities = MagicMock()

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    entities = async_add_entities.call_args.args[0]
    assert len(entities) == 2
    assert [entity.unique_id for entity in entities] == ["42_1", "42_2"]
    assert all(thermostat.update_async.await_count == 1 for thermostat in thermostats)
    assert async_add_entities.call_args.args[1] is False
    assert mock_py_touchline.call_args_list == [
        ((), {"hass": hass, "id": 0, "url": "http://127.0.0.2"}),
        ((), {"hass": hass, "id": 1, "url": "http://127.0.0.2"}),
    ]


@patch("custom_components.touchline.climate.HassTouchline")
async def test_climate_setup_entry_initialization_failure(
    mock_py_touchline, hass, mock_config_entry
):
    """A thermostat that cannot initialize makes config-entry setup retry."""
    controller = MagicMock()
    controller.get_number_of_devices_async = AsyncMock(return_value=1)
    hass.data[DOMAIN] = {mock_config_entry.entry_id: controller}
    thermostat = make_thermostat()
    thermostat.update_async.side_effect = ConnectionError
    mock_py_touchline.return_value = thermostat

    with pytest.raises(ConfigEntryNotReady):
        await async_setup_entry(hass, mock_config_entry, MagicMock())


async def test_touchline_entity_initialization_uses_native_temperature_and_string_ids():
    """IDs and temperature values are initialized before registry registration."""
    entity = Touchline(make_thermostat(device_id=3, controller_id=12))

    assert entity.unique_id == "12_3"
    assert entity.legacy_unique_id == "123"
    assert entity._attr_native_current_temperature == 21.0
    assert entity._attr_native_target_temperature == 22.0
    assert entity._attr_native_temperature_unit == "°C"
    assert entity.device_info["identifiers"] == {(DOMAIN, "12_3")}


@pytest.mark.parametrize(
    ("operation_mode", "week_program", "expected"),
    [
        (0, 0, "none"),
        (1, 0, "sleep"),
        (2, 0, "away"),
        (0, 1, "program_1"),
        (0, 2, "program_2"),
        (0, 3, "program_3"),
    ],
)
async def test_touchline_entity_preset_modes(operation_mode, week_program, expected):
    """Map Touchline operation settings to standard Home Assistant presets."""
    thermostat = make_thermostat()
    thermostat.get_operation_mode.return_value = operation_mode
    thermostat.get_week_program.return_value = week_program

    entity = Touchline(thermostat)

    assert entity.preset_mode == expected
    assert entity.preset_modes == [
        "none",
        "sleep",
        "away",
        "program_1",
        "program_2",
        "program_3",
    ]


async def test_touchline_entity_sets_standard_preset_and_native_temperature():
    """Writes use the preset mapping and native target temperature attribute."""
    thermostat = make_thermostat()
    entity = Touchline(thermostat)

    await entity.async_set_preset_mode("program_2")
    await entity.async_set_temperature(temperature=24.0)

    thermostat.set_operation_mode_async.assert_awaited_once_with(0)
    thermostat.set_week_program_async.assert_awaited_once_with(2)
    thermostat.set_target_temperature_async.assert_awaited_once_with(24.0)
    assert entity._attr_native_target_temperature == 24.0


async def test_touchline_entity_update_failure():
    """A failed update marks the entity unavailable."""
    thermostat = make_thermostat()
    entity = Touchline(thermostat)
    thermostat.update_async.side_effect = ConnectionError("Controller offline")

    await entity.async_update()

    assert entity.available is False


@patch("custom_components.touchline.climate.HassTouchline")
async def test_legacy_entity_id_migrates_when_unambiguous(
    mock_py_touchline, hass, mock_config_entry
):
    """The old concatenated registry ID keeps its entity ID during migration."""
    registry = er.async_get(hass)
    old_entry = registry.async_get_or_create(
        "climate",
        DOMAIN,
        "421",
        suggested_object_id="thermostat",
        config_entry=mock_config_entry,
    )
    controller = MagicMock()
    controller.get_number_of_devices_async = AsyncMock(return_value=1)
    hass.data[DOMAIN] = {mock_config_entry.entry_id: controller}
    mock_py_touchline.return_value = make_thermostat(device_id=1, controller_id=42)

    await async_setup_entry(hass, mock_config_entry, MagicMock())

    assert (
        registry.async_get_entity_id("climate", DOMAIN, "42_1")
        == old_entry.entity_id
    )


@patch("custom_components.touchline.climate.HassTouchline")
async def test_ambiguous_legacy_entity_id_is_not_migrated(
    mock_py_touchline, hass, mock_config_entry
):
    """An ambiguous concatenated ID is left intact rather than misassigned."""
    registry = er.async_get(hass)
    old_entry = registry.async_get_or_create(
        "climate",
        DOMAIN,
        "123",
        suggested_object_id="thermostat",
        config_entry=mock_config_entry,
    )
    controller = MagicMock()
    controller.get_number_of_devices_async = AsyncMock(return_value=2)
    hass.data[DOMAIN] = {mock_config_entry.entry_id: controller}
    mock_py_touchline.side_effect = [
        make_thermostat(device_id=23, controller_id=1),
        make_thermostat(device_id=3, controller_id=12),
    ]

    await async_setup_entry(hass, mock_config_entry, MagicMock())

    assert registry.async_get_entity_id("climate", DOMAIN, "123") == old_entry.entity_id
    assert registry.async_get_entity_id("climate", DOMAIN, "1_23") is None
    assert registry.async_get_entity_id("climate", DOMAIN, "12_3") is None


@patch("custom_components.touchline.climate.HassTouchline")
async def test_legacy_entity_id_from_another_entry_is_not_migrated(
    mock_py_touchline, hass, mock_config_entry
):
    """A matching legacy ID owned by a different entry is left untouched."""
    registry = er.async_get(hass)
    other_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "http://127.0.0.3"},
        entry_id="other_entry_id",
    )
    other_entry.add_to_hass(hass)
    old_entry = registry.async_get_or_create(
        "climate",
        DOMAIN,
        "421",
        suggested_object_id="other_thermostat",
        config_entry=other_entry,
    )
    controller = MagicMock()
    controller.get_number_of_devices_async = AsyncMock(return_value=1)
    hass.data[DOMAIN] = {mock_config_entry.entry_id: controller}
    mock_py_touchline.return_value = make_thermostat(device_id=1, controller_id=42)

    await async_setup_entry(hass, mock_config_entry, MagicMock())

    assert registry.async_get_entity_id("climate", DOMAIN, "421") == old_entry.entity_id
    assert registry.async_get_entity_id("climate", DOMAIN, "42_1") is None
