"""DataUpdateCoordinator for IPP Advanced.

Kernidee: Wenn der Drucker nicht erreichbar ist (ausgeschaltet, Netzwerkfehler),
wird NICHT UpdateFailed geworfen (das würde alle Entities auf 'unavailable'
setzen), sondern der zuletzt erfolgreich gelesene Datensatz wird einfach
weitergegeben. So bleiben Werte wie Tonerstand etc. sichtbar, auch wenn der
Drucker gerade offline ist.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from pyipp import IPP, IPPConnectionError, IPPConnectionUpgradeRequired, IPPError
from pyipp.models import Printer

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_BASE_PATH, LOGGER, SCAN_INTERVAL


@dataclass
class IPPAdvancedData:
    """Container für die zuletzt bekannten Druckerdaten."""

    printer: Printer
    available: bool
    last_update_success: bool


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

        super().__init__(
            hass,
            LOGGER,
            name=f"{host}",
            update_interval=SCAN_INTERVAL,
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
        return IPPAdvancedData(printer=printer, available=True, last_update_success=True)
