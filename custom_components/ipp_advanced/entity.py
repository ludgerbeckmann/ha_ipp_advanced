"""Gemeinsame Entity-Basisklasse für IPP Advanced (von sensor.py und
binary_sensor.py verwendet)."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_SSL
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import IPPAdvancedDataUpdateCoordinator


class IPPAdvancedBaseEntity(CoordinatorEntity[IPPAdvancedDataUpdateCoordinator]):
    """Gemeinsame Basis für alle Entities dieser Integration."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: IPPAdvancedDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry

    @property
    def device_info(self) -> DeviceInfo:
        printer = self.coordinator.data.printer
        scheme = "https" if self._entry.data.get(CONF_SSL) else "http"
        host = self._entry.data[CONF_HOST]
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=printer.info.name if printer else self._entry.title,
            manufacturer=printer.info.manufacturer if printer else None,
            model=printer.info.model if printer else None,
            # Zeigt Host/IP-Adresse als klickbaren Link auf der Geräteseite an
            # (HA hat kein eigenes "IP-Adresse"-Textfeld dort). Bewusst ohne den
            # IPP-Port (meist 631) - das eingebettete Web-Interface der meisten
            # Drucker läuft auf dem Standard-HTTP(S)-Port.
            configuration_url=f"{scheme}://{host}/",
            sw_version=printer.info.version if printer else None,
            serial_number=printer.info.serial if printer else None,
        )

    @property
    def available(self) -> bool:
        # Diese Integration meldet Entities praktisch immer als verfügbar,
        # solange wir jemals erfolgreich Daten gelesen haben - das ist der
        # ganze Sinn der "Persistent"-Variante.
        return self.coordinator.data.available
