"""DataUpdateCoordinator for IPP Advanced.

Kernidee: Wenn der Drucker nicht erreichbar ist (ausgeschaltet, Netzwerkfehler)
UND es bereits einen zuletzt erfolgreich gelesenen Datensatz gibt, wird NICHT
UpdateFailed geworfen (das würde alle Entities auf 'unavailable' setzen),
sondern dieser zwischengespeicherte Datensatz wird einfach weitergegeben. So
bleiben Werte wie Tonerstand etc. sichtbar, auch wenn der Drucker gerade
offline ist.

Dieser Zwischenspeicher wird zusätzlich auf die Festplatte geschrieben
(_store) und beim Start geladen (async_load_cached_printer) - sonst würde ein
Home-Assistant-Neustart bei zufällig gerade ausgeschaltetem Drucker den
In-Memory-Cache verlieren und die Entities gar nicht erst anlegen (siehe
async_load_cached_printer für Details).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from pyipp import IPP, IPPConnectionError, IPPConnectionUpgradeRequired, IPPError
from pyipp.models import Info, Marker, Printer, State, Uri

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_BASE_PATH, DEFAULT_SCAN_INTERVAL, DOMAIN, LOGGER

STORAGE_VERSION = 1


@dataclass
class IPPAdvancedData:
    """Container für die zuletzt bekannten Druckerdaten."""

    printer: Printer
    available: bool
    last_update_success: bool


def _printer_to_storage(printer: Printer) -> dict[str, Any]:
    """Printer in eine JSON-taugliche Form für den Store bringen."""
    data = printer.as_dict()
    data["booted_at"] = printer.booted_at.isoformat() if printer.booted_at else None
    return data


def _printer_from_storage(data: dict[str, Any]) -> Printer:
    """Gegenstück zu _printer_to_storage()."""
    booted_at = data["booted_at"]
    return Printer(
        info=Info(**data["info"]),
        markers=[Marker(**marker) for marker in data["markers"]],
        state=State(**data["state"]),
        uris=[Uri(**uri) for uri in data["uris"]],
        booted_at=datetime.fromisoformat(booted_at) if booted_at else None,
    )


class IPPAdvancedDataUpdateCoordinator(DataUpdateCoordinator[IPPAdvancedData]):
    """Coordinator, der bei Verbindungsfehlern den letzten Stand hält."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        host: str,
        port: int,
        base_path: str = DEFAULT_BASE_PATH,
        tls: bool = False,
        verify_ssl: bool = False,
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
    ) -> None:
        """Initialize."""
        self.host = host
        self.ipp = IPP(
            host=host,
            port=port,
            base_path=base_path,
            tls=tls,
            verify_ssl=verify_ssl,
            session=None,
        )

        # Hier landet der letzte erfolgreich gelesene Printer-Datensatz.
        self._last_printer: Printer | None = None
        self._consecutive_failures = 0
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}_{host}_printer"
        )

        super().__init__(
            hass,
            LOGGER,
            name=f"{host}",
            update_interval=timedelta(seconds=scan_interval),
        )

    @property
    def consecutive_failures(self) -> int:
        """Anzahl aufeinanderfolgender fehlgeschlagener Polls (für Diagnose)."""
        return self._consecutive_failures

    async def async_load_cached_printer(self) -> None:
        """Vor dem ersten Poll aufrufen: zuletzt gespeicherten Druckerzustand
        von der Platte laden.

        Ohne das würde ein Home-Assistant-Neustart bei zufällig gerade
        ausgeschaltetem Drucker den In-Memory-Cache verlieren: der erste Poll
        dieser Coordinator-Instanz schlägt fehl, es gibt (noch) keinen
        zwischengespeicherten Wert, also wirft _async_update_data() unten
        UpdateFailed -> ConfigEntryNotReady -> "Einrichtungsfehler, wird
        erneut versucht" - obwohl der Drucker vor dem Neustart problemlos
        erreichbar war. Mit dem hier geladenen Wert greift stattdessen sofort
        der normale Cache-Fallback-Pfad.
        """
        try:
            stored = await self._store.async_load()
        except Exception:  # noqa: BLE001 - beschädigte/inkompatible Store-Datei nicht fatal
            LOGGER.debug(
                "Zwischengespeicherten Druckerzustand für %s konnte nicht geladen werden",
                self.host,
                exc_info=True,
            )
            return
        if stored is None:
            return
        try:
            self._last_printer = _printer_from_storage(stored)
        except Exception:  # noqa: BLE001 - z.B. altes/inkompatibles Datenformat
            LOGGER.debug(
                "Zwischengespeicherter Druckerzustand für %s ist ungültig",
                self.host,
                exc_info=True,
            )

    async def _async_update_data(self) -> IPPAdvancedData:
        """Fetch data from the printer, falling back to cached data on error."""
        try:
            printer = await self.ipp.printer()
        except (IPPConnectionError, IPPConnectionUpgradeRequired, IPPError, OSError) as error:
            self._consecutive_failures += 1

            if self._last_printer is not None:
                LOGGER.debug(
                    "Drucker %s nicht erreichbar (%s), verwende zwischengespeicherte "
                    "Werte (Fehler seit %s Versuchen)",
                    self.host,
                    error,
                    self._consecutive_failures,
                )
                # Wichtig: Wir geben hier erfolgreich Daten zurück (kein raise),
                # damit der Coordinator nicht last_update_success=False setzt
                # und die Entities nicht auf 'unavailable' fallen. last_update_success
                # im Rückgabewert markiert trotzdem, dass es sich um zwischengespeicherte
                # statt frische Werte handelt (siehe sensor.py, offline_cached).
                return IPPAdvancedData(
                    printer=self._last_printer,
                    available=True,
                    last_update_success=False,
                )

            # Noch nie erfolgreich Daten geholt -> es gibt nichts zum Zwischenspeichern.
            # Hier MUSS ein echter Fehler geworfen werden: async_config_entry_first_refresh()
            # (siehe __init__.py) erkennt einen Fehlschlag nur über eine Exception. Ohne den
            # raise würde die Config Entry trotzdem eingerichtet, aber sensor.py stürzt beim
            # Anlegen der Entities ab (printer.markers auf None) - der Eintrag stünde am Ende
            # ganz ohne Entities da.
            LOGGER.warning("Drucker %s nicht erreichbar und keine zwischengespeicherten Werte vorhanden: %s", self.host, error)
            raise UpdateFailed(f"Drucker {self.host} nicht erreichbar: {error}") from error

        self._consecutive_failures = 0
        self._last_printer = printer
        await self._store.async_save(_printer_to_storage(printer))
        return IPPAdvancedData(printer=printer, available=True, last_update_success=True)
