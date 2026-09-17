"""Diagnostics-Unterstützung für IPP Advanced.

Über "Diagnose herunterladen" im Drei-Punkte-Menü eines Eintrags
(Einstellungen → Geräte & Dienste → IPP Advanced) als JSON-Datei abrufbar.
Liefert die Konfiguration (Host redigiert) sowie den zuletzt bekannten
Druckerzustand samt Cache-/Fehlerstatus, damit sich Verbindungs- oder
Cache-Probleme ohne manuelles Abschreiben von Werten nachvollziehen lassen.
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .coordinator import IPPAdvancedDataUpdateCoordinator

# Der Host verrät die Netzwerkadresse des Druckers - für die Ferndiagnose
# nicht nötig, alle anderen Config-Werte (Port, TLS, Base Path) schon.
TO_REDACT = {CONF_HOST}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Diagnose-Daten für einen Drucker-Eintrag."""
    coordinator: IPPAdvancedDataUpdateCoordinator = entry.runtime_data
    data = coordinator.data

    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "entry_options": dict(entry.options),
        "coordinator": {
            "available": data.available,
            "last_update_success": data.last_update_success,
            "consecutive_failures": coordinator.consecutive_failures,
        },
        "printer": data.printer.as_dict() if data.printer else None,
    }
