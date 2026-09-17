"""Tests fuer IPPAdvancedReachableSensor (binary_sensor.py)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from pyipp.models import Info, Printer, State

from custom_components.ipp_advanced.binary_sensor import IPPAdvancedReachableSensor
from custom_components.ipp_advanced.coordinator import IPPAdvancedData


def _make_printer() -> Printer:
    return Printer(
        info=Info(
            name="Test Printer", printer_name="test", printer_uri_supported=[], uptime=100
        ),
        markers=[],
        state=State(printer_state="idle", reasons=None, message=None),
        uris=[],
        booted_at=None,
    )


def _make_coordinator(last_update_success: bool) -> MagicMock:
    coordinator = MagicMock()
    coordinator.data = IPPAdvancedData(
        printer=_make_printer(), available=True, last_update_success=last_update_success
    )
    return coordinator


def _make_entry() -> SimpleNamespace:
    return SimpleNamespace(
        entry_id="entry123",
        title="Test Printer",
        data={"host": "10.0.0.5", "port": 631, "ssl": False},
    )


def test_reachable_sensor_is_on_when_live():
    sensor = IPPAdvancedReachableSensor(_make_coordinator(True), _make_entry())
    assert sensor.is_on is True


def test_reachable_sensor_is_off_when_using_cache():
    sensor = IPPAdvancedReachableSensor(_make_coordinator(False), _make_entry())
    assert sensor.is_on is False
