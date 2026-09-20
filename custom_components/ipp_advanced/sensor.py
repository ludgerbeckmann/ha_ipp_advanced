"""Sensor platform for IPP Advanced."""
from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from .coordinator import IPPAdvancedDataUpdateCoordinator
from .entity import IPPAdvancedBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up IPP Advanced sensors based on a config entry."""
    coordinator: IPPAdvancedDataUpdateCoordinator = entry.runtime_data

    printer = coordinator.data.printer
    entities: list[SensorEntity] = [
        IPPAdvancedPrinterStateSensor(coordinator, entry),
        IPPAdvancedLastBootSensor(coordinator, entry),
    ]

    # Für jedes Verbrauchsmaterial (Toner, Tinte, Trommel, ...) einen Sensor anlegen.
    for marker in printer.markers:
        entities.append(IPPAdvancedMarkerSensor(coordinator, entry, marker.marker_id))

    async_add_entities(entities)


class IPPAdvancedMarkerSensor(IPPAdvancedBaseEntity, RestoreEntity, SensorEntity):
    """Sensor für ein einzelnes Verbrauchsmaterial (z.B. Toner Schwarz)."""

    _attr_native_unit_of_measurement = "%"
    _attr_icon = "mdi:water"
    # Ohne state_class erzeugte Home Assistant für diesen numerischen Sensor
    # keine Langzeitstatistik/Verlaufsgrafik und meldete irgendwann die
    # Reparatur "Entität hat keine Zustandsklasse mehr". Core's eigene
    # ipp-Integration setzt für ihren Marker-Sensor genau das Gleiche.
    _attr_state_class = SensorStateClass.MEASUREMENT

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
            # Manche Drucker melden -1/-2 für "Füllstand unbekannt" statt
            # einen Prozentwert - das würde als Messwert (state_class
            # measurement) irreführend aussehen.
            return marker.level if marker.level >= 0 else None
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
    """Sensor für den generellen Druckerstatus (idle/processing/stopped/unreachable)."""

    _attr_translation_key = "printer_state"
    _attr_icon = "mdi:printer"
    _attr_device_class = SensorDeviceClass.ENUM
    # Rohwerte, die native_value liefern kann - Home Assistant übersetzt diese
    # über strings.json/translations/*.json (entity.sensor.printer_state.state.*)
    # automatisch in die jeweilige Sprache der Oberfläche.
    _attr_options = ["idle", "printing", "stopped", "unreachable"]

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
        data = self.coordinator.data
        if data.printer is not None:
            # Ohne aktuellen Poll den zwischengespeicherten Status (z.B.
            # "Leerlauf") anzuzeigen wäre irreführend, wenn der Drucker in
            # Wirklichkeit einfach ausgeschaltet ist - stattdessen "Nicht
            # erreichbar" zeigen.
            if not data.last_update_success:
                return "unreachable"
            return data.printer.state.printer_state
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


class IPPAdvancedLastBootSensor(IPPAdvancedBaseEntity, RestoreEntity, SensorEntity):
    """Sensor für den Zeitpunkt des letzten bekannten Starts des Druckers.

    "Letzter Start" statt "Letzter Neustart" im Namen - Letzteres klingt so,
    als liefe der Drucker gerade; der Wert bleibt aber unverändert stehen,
    solange der Drucker nicht erreichbar ist (siehe printer_state, das dann
    "unreachable" zeigt).

    Ein Timestamp-Sensor statt einer laufenden Sekundenzahl - das ist auch
    der Ansatz von Home Assistants eigenen system_monitor-/uptime-
    Integrationen ("Last Boot"). Der Wert ändert sich nur, wenn der Drucker
    tatsächlich neu startet (statt bei jedem Poll), und Home Assistant
    zeigt ihn im Frontend automatisch als relative Zeit an (z.B. "vor 3
    Tagen") - auch für sehr lange Laufzeiten besser lesbar als ein
    Sekundenwert.
    """

    _attr_translation_key = "last_boot"
    _attr_icon = "mdi:restart"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self,
        coordinator: IPPAdvancedDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_last_boot"
        self._restored_value: datetime | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            self._restored_value = dt_util.parse_datetime(last_state.state)

    @property
    def native_value(self) -> datetime | None:
        printer = self.coordinator.data.printer
        if printer is not None:
            return printer.booted_at
        return self._restored_value
