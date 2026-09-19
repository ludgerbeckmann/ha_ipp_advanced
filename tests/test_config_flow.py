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
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL, CONF_SSL, CONF_VERIFY_SSL
from homeassistant.data_entry_flow import FlowResultType

from custom_components.ipp_advanced.config_flow import (
    IPPAdvancedConfigFlow,
    IPPAdvancedOptionsFlow,
    STEP_USER_DATA_SCHEMA_WITH_SCAN_INTERVAL,
)
from custom_components.ipp_advanced.const import (
    CONF_BASE_PATH,
    CONF_NOTIFY_MARKER_LOW_THRESHOLD,
    CONF_NOTIFY_PERSISTENT,
    CONF_NOTIFY_REASONS,
    CONF_NOTIFY_TARGETS,
    NOTIFY_REASON_MARKER_EMPTY,
)


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


async def test_options_flow_schema_offers_notify_settings():
    flow = _make_flow()

    result = await flow.async_step_init()

    schema_keys = {str(key) for key in result["data_schema"].schema}
    assert CONF_NOTIFY_REASONS in schema_keys
    assert CONF_NOTIFY_MARKER_LOW_THRESHOLD in schema_keys
    assert CONF_NOTIFY_TARGETS in schema_keys
    assert CONF_NOTIFY_PERSISTENT in schema_keys


async def test_options_flow_saves_notify_settings():
    flow = _make_flow()

    result = await flow.async_step_init(
        {
            CONF_SCAN_INTERVAL: 60,
            CONF_NOTIFY_REASONS: [NOTIFY_REASON_MARKER_EMPTY],
            CONF_NOTIFY_MARKER_LOW_THRESHOLD: 20,
            CONF_NOTIFY_TARGETS: ["notify.mobile_app_phone"],
            CONF_NOTIFY_PERSISTENT: False,
        }
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_NOTIFY_REASONS] == [NOTIFY_REASON_MARKER_EMPTY]
    assert result["data"][CONF_NOTIFY_MARKER_LOW_THRESHOLD] == 20
    assert result["data"][CONF_NOTIFY_TARGETS] == ["notify.mobile_app_phone"]
    assert result["data"][CONF_NOTIFY_PERSISTENT] is False


async def test_options_flow_marker_low_threshold_schema_validates_choices():
    """Der Schwellwert kommt als Dropdown mit festen Prozent-Stufen - die
    Auswahl-Validierung (SelectSelector) + Coerce(int) muss einen der
    definierten Werte akzeptieren und als int zurueckgeben."""
    flow = _make_flow()

    result = await flow.async_step_init()
    validated = result["data_schema"]({CONF_SCAN_INTERVAL: 60, CONF_NOTIFY_MARKER_LOW_THRESHOLD: "20"})

    assert validated[CONF_NOTIFY_MARKER_LOW_THRESHOLD] == 20


def test_user_step_schema_offers_scan_interval():
    # Das Abfrageintervall soll schon beim Hinzufuegen eines neuen Druckers
    # einstellbar sein, nicht erst hinterher ueber die Options.
    assert CONF_SCAN_INTERVAL in STEP_USER_DATA_SCHEMA_WITH_SCAN_INTERVAL.schema


async def test_user_step_stores_scan_interval_as_option_not_data():
    """scan_interval landet in options (wie der Options Flow es liest),
    nicht in data - sonst wuerde der Coordinator es nie finden
    (entry.options.get(CONF_SCAN_INTERVAL, ...), siehe __init__.py)."""
    flow = IPPAdvancedConfigFlow()
    flow.hass = MagicMock()
    flow.context = {}
    flow.flow_id = "test-flow"
    flow.handler = "ipp_advanced"

    fake_printer = SimpleNamespace(info=SimpleNamespace(uuid="uuid-1", name="Test Printer"))

    with (
        patch(
            "custom_components.ipp_advanced.config_flow._async_try_connect",
            new=AsyncMock(return_value=(fake_printer, None)),
        ),
        patch.object(IPPAdvancedConfigFlow, "async_set_unique_id", new=AsyncMock()),
        patch.object(IPPAdvancedConfigFlow, "_abort_if_unique_id_configured", new=MagicMock()),
    ):
        result = await flow.async_step_user(
            {
                CONF_HOST: "10.0.0.5",
                CONF_PORT: 631,
                CONF_BASE_PATH: "/ipp/print",
                CONF_SSL: False,
                CONF_VERIFY_SSL: False,
                CONF_SCAN_INTERVAL: 90,
            }
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["options"] == {CONF_SCAN_INTERVAL: 90}
    assert CONF_SCAN_INTERVAL not in result["data"]
