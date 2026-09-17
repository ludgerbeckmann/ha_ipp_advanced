"""Tests fuer IPPAdvancedDataUpdateCoordinator._async_update_data().

Deckt genau das Verhalten ab, das den "keine Entities"-Bug verursacht
hat: Beim allerersten Fehlschlag (noch nie erfolgreich gepollt) MUSS
UpdateFailed geworfen werden, sonst erkennt
async_config_entry_first_refresh() den Fehlschlag nicht und Home
Assistant richtet die Sensor-Plattform mit printer=None ein (siehe
sensor.py-Absturz in der Git-Historie).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from pyipp import IPPConnectionError
from pyipp.models import Info, Marker, Printer, State
import pytest
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.ipp_advanced.coordinator import IPPAdvancedDataUpdateCoordinator


def _make_printer(state: str = "idle") -> Printer:
    return Printer(
        info=Info(
            name="Test Printer",
            printer_name="test",
            printer_uri_supported=[],
            uptime=100,
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
        state=State(printer_state=state, reasons=None, message=None),
        uris=[],
        booted_at=None,
    )


def _make_coordinator() -> IPPAdvancedDataUpdateCoordinator:
    hass = MagicMock()
    coordinator = IPPAdvancedDataUpdateCoordinator(
        hass, host="10.0.0.5", port=631, scan_interval=30
    )
    coordinator.ipp = MagicMock()
    return coordinator


async def test_successful_update_returns_fresh_data():
    coordinator = _make_coordinator()
    printer = _make_printer()
    coordinator.ipp.printer = AsyncMock(return_value=printer)

    data = await coordinator._async_update_data()

    assert data.printer is printer
    assert data.available is True
    assert data.last_update_success is True
    assert coordinator.consecutive_failures == 0


async def test_failure_after_previous_success_falls_back_to_cache():
    coordinator = _make_coordinator()
    printer = _make_printer()
    coordinator.ipp.printer = AsyncMock(return_value=printer)
    await coordinator._async_update_data()

    # Zweiter Poll schlaegt fehl - es gibt aber schon einen Cache.
    coordinator.ipp.printer = AsyncMock(side_effect=IPPConnectionError("offline"))
    data = await coordinator._async_update_data()

    assert data.printer is printer
    assert data.available is True
    # last_update_success=False markiert "das sind Cache-Werte, kein Live-Poll".
    assert data.last_update_success is False
    assert coordinator.consecutive_failures == 1


async def test_first_ever_failure_raises_update_failed():
    """Ohne vorherigen erfolgreichen Poll gibt es nichts zum
    Zwischenspeichern - hier MUSS eine Exception fliegen, sonst erkennt
    async_config_entry_first_refresh() den Fehlschlag nicht (siehe
    Docstring des Moduls und Git-Historie)."""
    coordinator = _make_coordinator()
    coordinator.ipp.printer = AsyncMock(side_effect=IPPConnectionError("offline"))

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
