"""Tests for the Roth Touchline config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.touchline.const import DOMAIN


def mock_controller(mock_py_touchline, *, controller_id=42, connection_error=None):
    """Set up library mocks for a successful controller connection."""
    controller = MagicMock()
    controller.get_number_of_devices_async = AsyncMock(return_value=1)
    device = MagicMock()
    device.update_async = AsyncMock()
    device.get_controller_id.return_value = controller_id
    mock_py_touchline.side_effect = [controller, device]
    if connection_error:
        controller.get_number_of_devices_async.side_effect = connection_error


@patch("custom_components.touchline.config_flow.HassTouchline")
async def test_form_success(mock_py_touchline, hass: HomeAssistant):
    """A numeric controller ID is normalized to a string config-entry ID."""
    mock_controller(mock_py_touchline, controller_id=321)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: "127.0.0.1"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == "http://127.0.0.1"
    assert result["result"].unique_id == "321"
    assert mock_py_touchline.call_args_list == [
        ((), {"hass": hass, "url": "http://127.0.0.1"}),
        ((), {"hass": hass, "id": 0, "url": "http://127.0.0.1"}),
    ]


@patch("custom_components.touchline.config_flow.HassTouchline")
async def test_form_cannot_connect(mock_py_touchline, hass: HomeAssistant):
    """A connection error leaves the user on the form with an error."""
    mock_controller(mock_py_touchline, connection_error=ConnectionError)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: "127.0.0.1"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


@patch("custom_components.touchline.config_flow.HassTouchline")
async def test_already_configured_by_host(mock_py_touchline, hass: HomeAssistant):
    """A host cannot be configured more than once."""
    mock_controller(mock_py_touchline)
    first_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: "127.0.0.1"},
    )
    assert first_result["type"] is FlowResultType.CREATE_ENTRY

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: "127.0.0.1"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@patch("custom_components.touchline.config_flow.HassTouchline")
async def test_already_configured_by_controller_id(
    mock_py_touchline, hass: HomeAssistant
):
    """Different hosts reporting one controller ID cannot be configured twice."""
    mock_controller(mock_py_touchline, controller_id=321)
    first_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: "127.0.0.1"},
    )
    assert first_result["type"] is FlowResultType.CREATE_ENTRY

    mock_controller(mock_py_touchline, controller_id=321)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: "127.0.0.2"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_yaml_import_step_removed():
    """The config flow no longer accepts YAML import."""
    from custom_components.touchline.config_flow import TouchlineConfigFlow

    assert not hasattr(TouchlineConfigFlow, "async_step_import")