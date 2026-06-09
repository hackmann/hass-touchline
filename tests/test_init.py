"""Tests for Roth Touchline setup."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

# Import from the integration
from custom_components.touchline import async_setup_entry
from custom_components.touchline.const import DOMAIN


@pytest.fixture
def mock_config_entry():
    """Mock a config entry."""
    entry = MagicMock()
    entry.data = {CONF_HOST: "http://127.0.0.2"}
    entry.entry_id = "test_entry_id"
    entry.state = ConfigEntryState.NOT_LOADED
    return entry


@patch("custom_components.touchline.HassTouchline")
async def test_setup_entry_success(
    mock_hass_touchline, hass: HomeAssistant, mock_config_entry
):
    """Test successful setup of a config entry."""
    mock_instance = mock_hass_touchline.return_value
    mock_instance.get_number_of_devices_async = AsyncMock(return_value=5)

    with patch.object(
        hass.config_entries, "async_forward_entry_setups", return_value=True
    ) as mock_forward:
        assert await async_setup_entry(hass, mock_config_entry) is True

        assert DOMAIN in hass.data
        assert hass.data[DOMAIN][mock_config_entry.entry_id] == mock_instance
        assert mock_forward.called


@patch("custom_components.touchline.HassTouchline")
async def test_setup_entry_no_devices(
    mock_hass_touchline, hass: HomeAssistant, mock_config_entry
):
    """Test setup failure when no devices are found."""
    mock_instance = mock_hass_touchline.return_value
    mock_instance.get_number_of_devices_async = AsyncMock(return_value=0)

    with pytest.raises(ConfigEntryNotReady):
        await async_setup_entry(hass, mock_config_entry)


@patch("custom_components.touchline.HassTouchline")
async def test_setup_entry_exception(
    mock_hass_touchline, hass: HomeAssistant, mock_config_entry
):
    """Test setup failure when an exception occurs during device check."""
    mock_instance = mock_hass_touchline.return_value
    mock_instance.get_number_of_devices_async = AsyncMock(
        side_effect=Exception("Connection error")
    )

    with pytest.raises(Exception):
        await async_setup_entry(hass, mock_config_entry)
