"""Sensor platform for IPP Advanced."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import IPPAdvancedDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up IPP Advanced sensors based on a config entry."""
    coordinator: IPPAdvancedDataUpdateCoordinator = entry.runtime_data

    printer = coordinator.data.printer
    entities: list[SensorEntity] = [
        IPPAdvancedPrinterStateSensor(coordinator, entry)
    ]

    # Für jedes Verbrauchsmaterial (Toner, Tinte, Trommel, ...) einen Sensor anlegen.
    for marker in printer.markers:
        entities.append(IPPAdvancedMarkerSensor(coordinator, entry, marker.marker_id))

    async_add_entities(entities)


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


class IPPAdvancedMarkerSensor(IPPAdvancedBaseEntity, RestoreEntity, SensorEntity):
    """Sensor für ein einzelnes Verbrauchsmaterial (z.B. Toner Schwarz)."""

    _attr_native_unit_of_measurement = "%"
    _attr_icon = "mdi:water"

    def __init__(
        self,
        coordinator: IPPAdvancedDataUpdateCoordinator,
        entry: ConfigEntry,
        marker_id: int,
    ) -> None:
        super().__init__(coordinator, entry)
        self._marker_id = marker_id
        self._attr_unique_id = f"{entry.entry_id}_marker_{marker_id}"
        self._restored_value: str | None = None
        self._restored_name: str | None = None

    async def async_added_to_hass(self) -> None:
        """Beim Hinzufügen: letzten Zustand aus der HA-Datenbank wiederherstellen.

        Das greift nur in der kurzen Zeitspanne zwischen HA-Neustart und dem
        ersten erfolgreichen Poll - sobald der Coordinator einmal live Daten
        hatte, übernimmt dessen eigener Cache (coordinator._last_printer).
        """
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            self._restored_value = last_state.state
            self._restored_name = last_state.attributes.get("marker_name")

    def _current_marker(self):
        printer = self.coordinator.data.printer
        if printer is None:
            return None
        for marker in printer.markers:
            if marker.marker_id == self._marker_id:
                return marker
        return None

    @property
    def name(self) -> str:
        marker = self._current_marker()
        if marker is not None:
            return marker.name
        return self._restored_name or f"Marker {self._marker_id}"

    @property
    def native_value(self) -> str | int | None:
        marker = self._current_marker()
        if marker is not None:
            return marker.level
        # Drucker war seit dem letzten Neustart noch nie erreichbar:
        # auf den aus der HA-Datenbank wiederhergestellten Wert zurückfallen.
        return self._restored_value

    @property
    def extra_state_attributes(self) -> dict:
        marker = self._current_marker()
        if marker is None:
            return {}
        return {
            "marker_name": marker.name,
            "marker_type": marker.marker_type,
            "marker_low_level": marker.low_level,
            "marker_high_level": marker.high_level,
        }


class IPPAdvancedPrinterStateSensor(IPPAdvancedBaseEntity, RestoreEntity, SensorEntity):
    """Sensor für den generellen Druckerstatus (idle/processing/stopped/offline)."""

    _attr_translation_key = "printer_state"
    _attr_icon = "mdi:printer"
    _attr_device_class = SensorDeviceClass.ENUM
    # Rohwerte, die native_value liefern kann - Home Assistant übersetzt diese
    # über strings.json/translations/*.json (entity.sensor.printer_state.state.*)
    # automatisch in die jeweilige Sprache der Oberfläche.
    _attr_options = ["idle", "printing", "stopped", "offline_cached"]

    def __init__(
        self,
        coordinator: IPPAdvancedDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_state"
        self._restored_value: str | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            self._restored_value = last_state.state

    @property
    def native_value(self) -> str | None:
        printer = self.coordinator.data.printer
        if printer is not None:
            # Wenn der Coordinator gerade auf zwischengespeicherte Werte
            # zurückgefallen ist, weisen wir das hier explizit aus, statt
            # einfach "idle" vorzugaukeln. Achtung: coordinator.data.last_update_success
            # (unser eigenes Feld) statt coordinator.last_update_success (das
            # eingebaute Coordinator-Flag, das wegen des bewussten "kein raise" bei
            # zwischengespeicherten Werten nie False wird).
            if not self.coordinator.data.last_update_success:
                return "offline_cached"
            return printer.state.printer_state
        return self._restored_value

    @property
    def extra_state_attributes(self) -> dict:
        printer = self.coordinator.data.printer
        if printer is None:
            return {}
        # pyipp liefert diese Gründe/Meldungen bereits mit (z.B. "media-empty",
        # "toner-low"), bisher wurden sie aber nirgends ausgewertet - hilfreich,
        # um bei state=="stopped" auch zu sehen, woran es liegt.
        return {
            "state_reasons": printer.state.reasons,
            "state_message": printer.state.message,
        }
