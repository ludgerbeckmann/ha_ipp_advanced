"""Tests fuer IPPAdvancedDataUpdateCoordinator._async_update_data().

Deckt genau das Verhalten ab, das den "keine Entities"-Bug verursacht
hat: Beim allerersten Fehlschlag (noch nie erfolgreich gepollt) MUSS
UpdateFailed geworfen werden, sonst erkennt
async_config_entry_first_refresh() den Fehlschlag nicht und Home
Assistant richtet die Sensor-Plattform mit printer=None ein (siehe
sensor.py-Absturz in der Git-Historie).
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from pyipp import IPPConnectionError
from pyipp.models import Counters, Info, Marker, Printer, State, Status
import pytest
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util

from custom_components.ipp_advanced.coordinator import (
    IPPAdvancedDataUpdateCoordinator,
    _printer_from_storage,
    _printer_to_storage,
    _state_to_storage,
)


def _make_printer(state: str = "idle") -> Printer:
    return Printer(
        info=Info(
            name="Test Printer",
            printer_name="test",
            printer_uri_supported=[],
            uptime=100,
        ),
        counters=Counters(
            impressions_completed=None,
            impressions_completed_col={},
            pages_completed=42,
            media_sheets_completed=None,
            supported=("pages_completed",),
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
        status=Status(accepting_jobs=None, queued_jobs=None, alerts=[], media_ready=[]),
        input_trays=[],
        output_trays=[],
        uris=[],
        booted_at=None,
    )


def _make_coordinator() -> IPPAdvancedDataUpdateCoordinator:
    hass = MagicMock()
    coordinator = IPPAdvancedDataUpdateCoordinator(
        hass, entry=MagicMock(), host="10.0.0.5", port=631, scan_interval=30
    )
    coordinator.ipp = MagicMock()
    # Store schreibt echte Dateien über hass.async_add_executor_job - für
    # diese reinen Logik-Tests reicht ein Fake ohne Festplattenzugriff.
    coordinator._store = MagicMock()
    coordinator._store.async_load = AsyncMock(return_value=None)
    coordinator._store.async_save = AsyncMock()
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


async def test_successful_update_sets_last_seen():
    coordinator = _make_coordinator()
    printer = _make_printer()
    coordinator.ipp.printer = AsyncMock(return_value=printer)

    before = dt_util.utcnow()
    data = await coordinator._async_update_data()
    after = dt_util.utcnow()

    assert data.last_seen is not None
    assert before <= data.last_seen <= after


async def test_cache_fallback_keeps_previous_last_seen():
    # last_seen beschreibt "wann zuletzt tatsächlich verbunden" - ein
    # Rückfall auf den Cache ist per Definition keine neue Verbindung und
    # darf last_seen deshalb nicht verändern.
    coordinator = _make_coordinator()
    printer = _make_printer()
    coordinator.ipp.printer = AsyncMock(return_value=printer)
    first = await coordinator._async_update_data()

    coordinator.ipp.printer = AsyncMock(side_effect=IPPConnectionError("offline"))
    second = await coordinator._async_update_data()

    assert second.last_seen == first.last_seen


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


async def test_loaded_cache_prevents_update_failed_on_restart():
    """Simuliert einen HA-Neustart bei ausgeschaltetem Drucker: Ohne den
    von der Platte geladenen Cache wuerde der erste Poll dieser (neuen)
    Coordinator-Instanz mit UpdateFailed abbrechen ("Einrichtungsfehler,
    wird erneut versucht"), obwohl der Drucker vor dem Neustart erreichbar
    war.

    Nutzt bewusst das alte, flache Store-Format (Printer direkt auf
    oberster Ebene, ohne "printer"/"last_seen"-Verschachtelung) - das
    deckt gleichzeitig ab, dass Store-Dateien von vor der
    "Letzte Verbindung"-Umstellung noch geladen werden koennen."""
    coordinator = _make_coordinator()
    printer = _make_printer()
    coordinator._store.async_load = AsyncMock(return_value=_printer_to_storage(printer))

    await coordinator.async_load_cached_printer()
    coordinator.ipp.printer = AsyncMock(side_effect=IPPConnectionError("offline"))
    data = await coordinator._async_update_data()

    assert data.printer.info.name == printer.info.name
    assert data.available is True
    assert data.last_update_success is False
    assert data.last_seen is None


async def test_async_load_cached_printer_restores_last_seen_from_store():
    coordinator = _make_coordinator()
    printer = _make_printer()
    last_seen = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    coordinator._store.async_load = AsyncMock(
        return_value=_state_to_storage(printer, last_seen)
    )

    await coordinator.async_load_cached_printer()

    assert coordinator._last_seen == last_seen
    assert coordinator._last_printer.info.name == printer.info.name


async def test_async_load_cached_printer_ignores_missing_or_invalid_data():
    coordinator = _make_coordinator()
    await coordinator.async_load_cached_printer()
    assert coordinator._last_printer is None

    coordinator._store.async_load = AsyncMock(return_value={"garbage": True})
    await coordinator.async_load_cached_printer()
    assert coordinator._last_printer is None


async def test_first_ever_failure_raises_update_failed():
    """Ohne vorherigen erfolgreichen Poll gibt es nichts zum
    Zwischenspeichern - hier MUSS eine Exception fliegen, sonst erkennt
    async_config_entry_first_refresh() den Fehlschlag nicht (siehe
    Docstring des Moduls und Git-Historie)."""
    coordinator = _make_coordinator()
    coordinator.ipp.printer = AsyncMock(side_effect=IPPConnectionError("offline"))

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


def test_state_storage_roundtrip_keeps_last_seen():
    printer = _make_printer()
    last_seen = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    stored = _state_to_storage(printer, last_seen)

    assert stored["last_seen"] == last_seen.isoformat()
    assert _printer_from_storage(stored["printer"]).counters.pages_completed == 42


def test_state_storage_handles_missing_last_seen():
    stored = _state_to_storage(_make_printer(), last_seen=None)

    assert stored["last_seen"] is None


def test_printer_storage_roundtrip_keeps_counters():
    printer = _make_printer()
    stored = _printer_to_storage(printer)
    restored = _printer_from_storage(stored)

    assert restored.counters.pages_completed == 42
    assert restored.counters.supported == ("pages_completed",)


def test_printer_from_storage_defaults_counters_for_old_cache_files():
    """Store-Dateien, die vor der Umstellung auf aioipp geschrieben wurden,
    haben weder "counters" noch "status"/"input_trays"/"output_trays" -
    das darf beim Laden nicht mit einem KeyError abbrechen (siehe
    _printer_from_storage)."""
    printer = _make_printer()
    stored = _printer_to_storage(printer)
    del stored["counters"]
    del stored["status"]
    del stored["input_trays"]
    del stored["output_trays"]

    restored = _printer_from_storage(stored)

    assert restored.counters.pages_completed is None
    assert restored.counters.impressions_completed_col == {}
    assert restored.counters.supported == ()
    assert restored.status.alerts == []
    assert restored.input_trays == []
    assert restored.output_trays == []
