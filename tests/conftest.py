"""Shared Home Assistant test configuration."""

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading integrations from the custom_components directory."""
    yield