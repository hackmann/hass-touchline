"""Tests for Roth Touchline climate platform."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from custom_components.touchline.climate import async_setup_entry, Touchline
from custom_components.touchline.const import DOMAIN


@pytest.fixture
def mock_config_entry():
    """Mock a config entry."""
    entry = MagicMock()
    entry.data = {CONF_HOST: "http://127.0.0.2"}
    entry.entry_id = "test_entry_id"
    return entry


@patch("custom_components.touchline.climate.PyTouchline")
async def test_climate_setup_entry(
    mock_py_touchline, hass: HomeAssistant, mock_config_entry
):
    """Test climate setup entry."""
    mock_py_touchline_instance = MagicMock()
    mock_py_touchline_instance.get_number_of_devices_async = AsyncMock(return_value=1)
    
    # py_touchline instance stored in hass.data during __init__.async_setup_entry
    hass.data[DOMAIN] = {mock_config_entry.entry_id: mock_py_touchline_instance}

    async_add_entities = MagicMock()

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    # Verify update_before_add is False (second argument to async_add_entities)
    async_add_entities.assert_called_once()
    args, kwargs = async_add_entities.call_args
    assert args[1] is False
    assert len(args[0]) == 1
    assert isinstance(args[0][0], Touchline)


async def test_touchline_entity_update_success():
    """Test Touchline entity update success."""
    mock_unit = MagicMock()
    mock_unit.update_async = AsyncMock()
    mock_unit.get_name.return_value = "Test Room"
    mock_unit.get_device_id.return_value = "1"
    mock_unit.get_controller_id.return_value = "C"
    mock_unit.get_current_temperature.return_value = 21.0
    mock_unit.get_target_temperature.return_value = 22.0
    mock_unit.get_operation_mode.return_value = 0
    mock_unit.get_week_program.return_value = 0

    entity = Touchline(mock_unit)
    await entity.async_update()

    assert entity.available is True
    assert entity.name == "Test Room"
    assert entity.current_temperature == 21.0
    assert entity.target_temperature == 22.0


async def test_touchline_entity_update_failure():
    """Test Touchline entity update failure."""
    mock_unit = MagicMock()
    mock_unit.update_async = AsyncMock(side_effect=Exception("Connection error"))
    
    entity = Touchline(mock_unit)
    # Initially available is True by default in HA entities if not set otherwise, 
    # but let's see what happens after update fails.
    
    await entity.async_update()

    assert entity.available is False
