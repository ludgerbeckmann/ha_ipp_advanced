"""The IPP Advanced integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SSL,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant

from .const import CONF_BASE_PATH, DEFAULT_BASE_PATH, DEFAULT_SCAN_INTERVAL
from .coordinator import IPPAdvancedDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


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

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # Bei einer Options-Änderung (z.B. neues Abfrageintervall) oder einer
    # Reconfigure (neuer Host/Port über den Config Flow) neu laden, damit der
    # Coordinator mit den neuen Werten neu aufgebaut wird.
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Eintrag bei Options-/Daten-Änderung neu laden."""
    await hass.config_entries.async_reload(entry.entry_id)
