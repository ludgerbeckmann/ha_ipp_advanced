"""The IPP Advanced integration."""
from __future__ import annotations

from datetime import datetime
from functools import partial
from typing import Any

from pyipp import IPP, IPPConnectionError, IPPConnectionUpgradeRequired, IPPError
from pyipp.enums import IppOperation

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_ID,
    CONF_HOST,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SSL,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.helpers import device_registry as dr

from .const import CONF_BASE_PATH, DEFAULT_BASE_PATH, DEFAULT_SCAN_INTERVAL, DOMAIN
from .coordinator import IPPAdvancedDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]

SERVICE_ATTRIBUTE_DUMP = "attribute_dump"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up IPP Advanced from a config entry."""
    coordinator = IPPAdvancedDataUpdateCoordinator(
        hass,
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        base_path=entry.data.get(CONF_BASE_PATH, DEFAULT_BASE_PATH),
        tls=entry.data.get(CONF_SSL, False),
        verify_ssl=entry.data.get(CONF_VERIFY_SSL, False),
        scan_interval=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
    )

    # Zuletzt gespeicherten Druckerzustand laden, BEVOR der erste Poll
    # versucht wird - sonst würde ein Neustart bei zufällig gerade
    # ausgeschaltetem Drucker den Cache verlieren und "Einrichtungsfehler,
    # wird erneut versucht" auslösen, obwohl der Drucker vor dem Neustart
    # längst erfolgreich ausgelesen wurde (siehe coordinator.py).
    await coordinator.async_load_cached_printer()
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # Bei einer Options-Änderung (z.B. neues Abfrageintervall) oder einer
    # Reconfigure (neuer Host/Port über den Config Flow) neu laden, damit der
    # Coordinator mit den neuen Werten neu aufgebaut wird.
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    # Nur einmal registrieren, unabhängig davon, wie viele Drucker
    # konfiguriert sind.
    if not hass.services.has_service(DOMAIN, SERVICE_ATTRIBUTE_DUMP):
        hass.services.async_register(
            DOMAIN,
            SERVICE_ATTRIBUTE_DUMP,
            partial(_async_handle_attribute_dump, hass),
            supports_response=SupportsResponse.ONLY,
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Eintrag bei Options-/Daten-Änderung neu laden."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_handle_attribute_dump(
    hass: HomeAssistant, call: ServiceCall
) -> ServiceResponse:
    """Service ipp_advanced.attribute_dump: alle vom Drucker über IPP
    gemeldeten Attribute abfragen und zurückgeben.

    Nutzt bewusst die schon laufende Coordinator-Verbindung (coordinator.ipp)
    des ausgewählten Geräts - kein zusätzliches Gerät, kein SSH, kein
    separates Skript nötig, da die Integration ohnehin schon erfolgreich mit
    dem Drucker verbunden ist. Über Entwicklerwerkzeuge → Aktionen aufrufbar.
    """
    device_registry = dr.async_get(hass)
    printers: dict[str, Any] = {}

    for device_id in call.data[ATTR_DEVICE_ID]:
        device = device_registry.async_get(device_id)
        if device is None:
            continue

        entry = next(
            (
                found
                for entry_id in device.config_entries
                if (found := hass.config_entries.async_get_entry(entry_id)) is not None
                and found.domain == DOMAIN
            ),
            None,
        )
        if entry is None:
            continue

        coordinator: IPPAdvancedDataUpdateCoordinator = entry.runtime_data
        printers[entry.title] = await _async_dump_printer_attributes(coordinator.ipp)

    return {"printers": printers}


async def _async_dump_printer_attributes(ipp: IPP) -> dict[str, Any]:
    """Alle IPP-Attribute des Druckers abfragen (nicht nur die von pyipp's
    Printer-Modell ausgewerteten) - Gegenstück zum "requested-attributes":
    "all"-Aufruf, den man sonst nur per eigenem Skript absetzen könnte."""
    try:
        response = await ipp.execute(
            IppOperation.GET_PRINTER_ATTRIBUTES,
            {"operation-attributes-tag": {"requested-attributes": "all"}},
        )
    except (IPPConnectionUpgradeRequired, IPPConnectionError, IPPError, OSError) as error:
        return {"error": str(error)}

    attributes = next(iter(response["printers"]), {})
    return _json_safe(attributes)


def _json_safe(value: Any) -> Any:
    """Rohe IPP-Werte (u.a. datetime, tuple) in JSON-taugliche Werte für die
    Service-Response umwandeln."""
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    return value
