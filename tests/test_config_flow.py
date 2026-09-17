"""Tests fuer den Options Flow (Zahnrad-Symbol am Integrations-Eintrag).

Regressionstest fuer einen 500er ("Der Konfigurationsfluss konnte nicht
geladen werden") beim Oeffnen des Options-Flows: Home Assistant hat den
seit 2024.12 nur noch als deprecated markierten Setter fuer
OptionsFlow.config_entry in Version 2025.12 komplett entfernt. Ein eigener
__init__, der self.config_entry = config_entry zuweist, wirft seitdem
AttributeError ("property 'config_entry' has no setter"). Die Property
selbst wird vom Framework automatisch befuellt (ueber self.hass/self.handler),
ein eigenes __init__ ist dafuer nicht noetig.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.data_entry_flow import FlowResultType

from custom_components.ipp_advanced.config_flow import IPPAdvancedOptionsFlow


def _make_flow(entry_options: dict | None = None) -> IPPAdvancedOptionsFlow:
    flow = IPPAdvancedOptionsFlow()
    flow.hass = MagicMock()
    flow.hass.config_entries.async_get_known_entry.return_value = SimpleNamespace(
        options=entry_options or {}
    )
    flow.handler = "entry123"
    return flow


def test_options_flow_has_no_custom_init():
    # self.config_entry ist seit HA 2024.12 eine vom Framework befuellte
    # Property ohne Setter (seit 2025.12 sogar zwingend) - ein eigenes
    # __init__, das self.config_entry selbst zuweist, wirft AttributeError.
    assert IPPAdvancedOptionsFlow.__init__ is object.__init__


async def test_options_flow_shows_form_with_current_scan_interval():
    flow = _make_flow(entry_options={CONF_SCAN_INTERVAL: 45})

    result = await flow.async_step_init()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"


async def test_options_flow_saves_new_scan_interval():
    flow = _make_flow()

    result = await flow.async_step_init({CONF_SCAN_INTERVAL: 120})

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_SCAN_INTERVAL: 120}
