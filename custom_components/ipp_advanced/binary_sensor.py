"""Binary sensor platform for IPP Advanced."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import IPPAdvancedDataUpdateCoordinator
from .entity import IPPAdvancedBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the IPP Advanced connectivity binary sensor."""
    coordinator: IPPAdvancedDataUpdateCoordinator = entry.runtime_data
    async_add_entities([IPPAdvancedReachableSensor(coordinator, entry)])


class IPPAdvancedReachableSensor(IPPAdvancedBaseEntity, BinarySensorEntity):
    """Zeigt getrennt vom eigentlichen Druckerstatus an, ob der letzte Poll
    live erfolgreich war oder ob gerade zwischengespeicherte Werte
    angezeigt werden (siehe coordinator.py)."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_translation_key = "reachable"

    def __init__(
        self,
        coordinator: IPPAdvancedDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_reachable"

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.last_update_success
