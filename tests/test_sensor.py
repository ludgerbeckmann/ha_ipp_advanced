"""Tests fuer die Sensor-Entities.

Deckt genau die Absturz-Kette ab, die zu einem Eintrag ohne Entities
gefuehrt hat: device_info wird beim Registrieren jeder Entity von Home
Assistant abgerufen - ein falscher Attributname dort (siehe
tests/test_pyipp_model_usage.py) wuerde hier als AttributeError
auffallen, sobald device_info tatsaechlich aufgerufen wird.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from pyipp.models import Info, Marker, Printer, State

from custom_components.ipp_advanced.coordinator import IPPAdvancedData
from custom_components.ipp_advanced.sensor import (
    IPPAdvancedMarkerSensor,
    IPPAdvancedPrinterStateSensor,
)


def _make_printer(state: str = "idle", reasons=None, message=None) -> Printer:
    return Printer(
        info=Info(
            name="Test Printer",
            printer_name="test",
            printer_uri_supported=[],
            uptime=100,
            manufacturer="HP",
            model="Envy 6000",
            serial="ABC123",
            version="1.2.3",
        ),
        markers=[
            Marker(
                marker_id=1,
                marker_type="ink",
                name="Schwarz",
                color="#000000",
                level=50,
                low_level=10,
                high_level=100,
            )
        ],
        state=State(printer_state=state, reasons=reasons, message=message),
        uris=[],
        booted_at=None,
    )


def _make_coordinator(printer: Printer | None, last_update_success: bool = True) -> MagicMock:
    coordinator = MagicMock()
    coordinator.data = IPPAdvancedData(
        printer=printer, available=True, last_update_success=last_update_success
    )
    return coordinator


def _make_entry() -> SimpleNamespace:
    return SimpleNamespace(
        entry_id="entry123",
        title="Test Printer",
        data={"host": "10.0.0.5", "port": 631, "ssl": False},
    )


def test_device_info_uses_real_pyipp_fields():
    printer = _make_printer()
    coordinator = _make_coordinator(printer)
    sensor = IPPAdvancedPrinterStateSensor(coordinator, _make_entry())

    info = sensor.device_info

    assert info["name"] == "Test Printer"
    assert info["manufacturer"] == "HP"
    assert info["model"] == "Envy 6000"
    assert info["sw_version"] == "1.2.3"
    assert info["serial_number"] == "ABC123"
    assert info["configuration_url"] == "http://10.0.0.5/"


def test_state_sensor_reports_live_state():
    printer = _make_printer(state="printing")
    coordinator = _make_coordinator(printer, last_update_success=True)
    sensor = IPPAdvancedPrinterStateSensor(coordinator, _make_entry())

    assert sensor.native_value == "printing"


def test_state_sensor_reports_real_state_even_when_stale():
    # Seit der Aufteilung in einen separaten "Erreichbar"-Binärsensor
    # (binary_sensor.py) zeigt dieser Sensor immer den echten IPP-Status -
    # live oder zwischengespeichert macht dafuer keinen Unterschied mehr.
    printer = _make_printer(state="idle")
    coordinator = _make_coordinator(printer, last_update_success=False)
    sensor = IPPAdvancedPrinterStateSensor(coordinator, _make_entry())

    assert sensor.native_value == "idle"


def test_state_sensor_exposes_state_reasons():
    printer = _make_printer(state="stopped", reasons="media-empty", message="Kein Papier")
    coordinator = _make_coordinator(printer)
    sensor = IPPAdvancedPrinterStateSensor(coordinator, _make_entry())

    attrs = sensor.extra_state_attributes
    assert attrs["state_reasons"] == "media-empty"
    assert attrs["state_message"] == "Kein Papier"


def test_marker_sensor_reports_level_and_attributes():
    printer = _make_printer()
    coordinator = _make_coordinator(printer)
    sensor = IPPAdvancedMarkerSensor(coordinator, _make_entry(), marker_id=1)

    assert sensor.name == "Schwarz"
    assert sensor.native_value == 50
    assert sensor.extra_state_attributes == {
        "marker_name": "Schwarz",
        "marker_type": "ink",
        "marker_low_level": 10,
        "marker_high_level": 100,
    }


def test_marker_sensor_falls_back_to_restored_value_when_printer_missing():
    coordinator = _make_coordinator(printer=None)
    sensor = IPPAdvancedMarkerSensor(coordinator, _make_entry(), marker_id=1)
    sensor._restored_value = "37"
    sensor._restored_name = "Schwarz"

    assert sensor.name == "Schwarz"
    assert sensor.native_value == "37"
    assert sensor.extra_state_attributes == {}
