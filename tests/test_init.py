"""Tests for Roth Touchline setup."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_CLOSE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import httpx_client
from httpx import MockTransport, Response

# Import from the integration
from custom_components.touchline import HassTouchline, async_setup_entry
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
        mock_hass_touchline.assert_called_once_with(
            hass=hass, url=mock_config_entry.data[CONF_HOST]
        )


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

    with pytest.raises(ConfigEntryNotReady):
        await async_setup_entry(hass, mock_config_entry)


@patch("custom_components.touchline.httpx_client.create_async_httpx_client")
async def test_hass_touchline_shares_client_per_home_assistant(
    mock_create_client, hass: HomeAssistant
):
    """All Touchline objects for one Home Assistant share its managed client."""
    async_client = object()
    mock_create_client.return_value = async_client

    controller = HassTouchline(hass=hass, url="http://127.0.0.1")
    thermostat = HassTouchline(hass=hass, id=1, url="http://127.0.0.1")

    assert controller.get_async_client() is async_client
    assert thermostat.get_async_client() is async_client
    mock_create_client.assert_called_once_with(
        hass, verify_ssl=False, timeout=controller._timeout
    )


async def test_hass_touchline_reuses_client_for_requests_and_closes_on_shutdown(
    hass: HomeAssistant, monkeypatch
):
    """Read and write requests reuse the HA client until Home Assistant closes."""
    requests = []

    def handle_request(request):
        requests.append(request)
        content = b"<response />" if request.method == "POST" else b"2200"
        return Response(200, content=content)

    transport = MockTransport(handle_request)
    create_client = httpx_client.create_async_httpx_client
    mock_create_client = MagicMock(
        side_effect=lambda instance, **kwargs: create_client(
            instance, transport=transport, **kwargs
        )
    )
    monkeypatch.setattr(
        httpx_client, "create_async_httpx_client", mock_create_client
    )

    controller = HassTouchline(hass=hass, url="http://touchline.local")
    thermostat = HassTouchline(hass=hass, id=1, url="http://touchline.local")
    controller._parameter["Unique ID"] = "1"
    thermostat._parameter["Unique ID"] = "2"

    await controller._request_and_receive_xml("read-one")
    await thermostat._request_and_receive_xml("read-two")
    await controller.write_parameter_async("SollTemp", 2200)
    await thermostat.write_parameter_async("SollTemp", 2200)

    async_client = controller.get_async_client()
    assert thermostat.get_async_client() is async_client
    assert len(requests) == 4
    assert [request.method for request in requests] == ["POST", "POST", "GET", "GET"]
    assert not async_client.is_closed
    mock_create_client.assert_called_once()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_CLOSE)
    await hass.async_block_till_done()

    assert async_client.is_closed
