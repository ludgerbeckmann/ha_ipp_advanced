"""Tests fuer den Service ipp_advanced.attribute_dump.

Statt eines separaten Skripts (SSH/manuelle Installation noetig) laesst sich
damit ueber Entwicklerwerkzeuge -> Aktionen direkt in Home Assistant abfragen,
welche IPP-Attribute ein Drucker unterstuetzt - ueber die ohnehin schon
laufende Verbindung der Integration (coordinator.ipp).
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.const import ATTR_DEVICE_ID
from pyipp import IPPConnectionError

from custom_components.ipp_advanced import (
    DOMAIN,
    _async_dump_printer_attributes,
    _async_handle_attribute_dump,
    _json_safe,
)


def test_json_safe_converts_datetime_and_tuples():
    raw = {
        "printer-current-time": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "printer-resolution": (600, 600, 3),
        "nested": {"values": [1, "a", (2, 3)]},
    }

    safe = _json_safe(raw)

    assert safe["printer-current-time"] == "2026-01-01T00:00:00+00:00"
    assert safe["printer-resolution"] == [600, 600, 3]
    assert safe["nested"]["values"] == [1, "a", [2, 3]]


async def test_dump_printer_attributes_returns_json_safe_attributes():
    ipp = MagicMock()
    ipp.execute = AsyncMock(
        return_value={
            "printers": [
                {"printer-name": "Test", "printer-current-time": datetime(2026, 1, 1)}
            ]
        }
    )

    result = await _async_dump_printer_attributes(ipp)

    assert result == {
        "printer-name": "Test",
        "printer-current-time": "2026-01-01T00:00:00",
    }


async def test_dump_printer_attributes_reports_connection_error_as_result():
    """Ein nicht erreichbarer Drucker soll die Aktion nicht mit einer
    Exception abbrechen lassen, sondern den Fehler im Ergebnis zeigen -
    sonst waere die Fehlermeldung in Entwicklerwerkzeuge -> Aktionen kaum
    nutzbar (nur generischer 'Aktion fehlgeschlagen'-Text)."""
    ipp = MagicMock()
    ipp.execute = AsyncMock(side_effect=IPPConnectionError("offline"))

    result = await _async_dump_printer_attributes(ipp)

    assert "error" in result


async def test_handle_attribute_dump_looks_up_entry_via_device_registry():
    hass = MagicMock()
    fake_coordinator = SimpleNamespace(ipp=MagicMock())
    fake_entry = SimpleNamespace(
        domain=DOMAIN, title="Epson ET-3950", runtime_data=fake_coordinator
    )
    fake_device = SimpleNamespace(config_entries={"entry123"})

    device_registry = MagicMock()
    device_registry.async_get.return_value = fake_device
    hass.config_entries.async_get_entry.return_value = fake_entry

    call = SimpleNamespace(data={ATTR_DEVICE_ID: ["device123"]})

    with (
        patch("custom_components.ipp_advanced.dr.async_get", return_value=device_registry),
        patch(
            "custom_components.ipp_advanced._async_dump_printer_attributes",
            new=AsyncMock(return_value={"printer-name": "Epson ET-3950"}),
        ),
    ):
        result = await _async_handle_attribute_dump(hass, call)

    assert result == {"printers": {"Epson ET-3950": {"printer-name": "Epson ET-3950"}}}


async def test_handle_attribute_dump_skips_devices_from_other_domains():
    hass = MagicMock()
    fake_entry = SimpleNamespace(domain="other_domain", title="Fremd", runtime_data=None)
    fake_device = SimpleNamespace(config_entries={"entry123"})

    device_registry = MagicMock()
    device_registry.async_get.return_value = fake_device
    hass.config_entries.async_get_entry.return_value = fake_entry

    call = SimpleNamespace(data={ATTR_DEVICE_ID: ["device123"]})

    with patch("custom_components.ipp_advanced.dr.async_get", return_value=device_registry):
        result = await _async_handle_attribute_dump(hass, call)

    assert result == {"printers": {}}
