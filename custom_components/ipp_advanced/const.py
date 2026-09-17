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
