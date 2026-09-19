"""Constants for the IPP Advanced integration."""
from __future__ import annotations

import logging

DOMAIN = "ipp_advanced"
LOGGER = logging.getLogger(__package__)

DEFAULT_PORT = 631
DEFAULT_BASE_PATH = "/ipp/print"
DEFAULT_TLS = False
DEFAULT_VERIFY_SSL = False

# Abfrageintervall in Sekunden - Standardwert, falls in den Optionen des
# Eintrags nichts anderes hinterlegt ist (siehe config_flow.py, Options Flow).
DEFAULT_SCAN_INTERVAL = 60
MIN_SCAN_INTERVAL = 10
MAX_SCAN_INTERVAL = 3600

CONF_BASE_PATH = "base_path"

# Sensor keys we track from pyipp's Printer/Marker data.
# Wird zur Laufzeit dynamisch aus den Markern des Druckers erzeugt,
# diese Liste ist nur für statische Gerätewerte.
ATTR_PRINTER_STATE = "printer_state"
ATTR_PRINTER_INFO = "printer_info"

# Optionen für die Benachrichtigungsfunktion (siehe notifications.py und der
# Options Flow in config_flow.py) - je Eintrag/Drucker konfigurierbar.
CONF_NOTIFY_TARGETS = "notify_targets"
CONF_NOTIFY_PERSISTENT = "notify_persistent"
CONF_NOTIFY_REASONS = "notify_reasons"
DEFAULT_NOTIFY_PERSISTENT = True

NOTIFY_REASON_MARKER_EMPTY = "marker_empty"
NOTIFY_REASON_MARKER_LOW = "marker_low"
NOTIFY_REASON_MEDIA_EMPTY = "media_empty"
NOTIFY_REASON_MEDIA_JAM = "media_jam"
NOTIFY_REASON_COVER_OPEN = "cover_open"
NOTIFY_REASON_PRINTER_STOPPED = "printer_stopped"
NOTIFY_REASON_PRINTER_UNREACHABLE = "printer_unreachable"

# Reihenfolge bestimmt die Anzeige-Reihenfolge in der Options-Auswahl.
NOTIFY_REASONS = [
    NOTIFY_REASON_MARKER_EMPTY,
    NOTIFY_REASON_MARKER_LOW,
    NOTIFY_REASON_MEDIA_EMPTY,
    NOTIFY_REASON_MEDIA_JAM,
    NOTIFY_REASON_COVER_OPEN,
    NOTIFY_REASON_PRINTER_STOPPED,
    NOTIFY_REASON_PRINTER_UNREACHABLE,
]
