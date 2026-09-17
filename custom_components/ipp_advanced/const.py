"""Constants for the IPP Advanced integration."""
from __future__ import annotations

from datetime import timedelta
import logging

DOMAIN = "ipp_advanced"
LOGGER = logging.getLogger(__package__)

DEFAULT_PORT = 631
DEFAULT_BASE_PATH = "/ipp/print"
DEFAULT_TLS = False
DEFAULT_VERIFY_SSL = False

SCAN_INTERVAL = timedelta(seconds=60)

CONF_BASE_PATH = "base_path"

# Sensor keys we track from pyipp's Printer/Marker data.
# Wird zur Laufzeit dynamisch aus den Markern des Druckers erzeugt,
# diese Liste ist nur für statische Gerätewerte.
ATTR_PRINTER_STATE = "printer_state"
ATTR_PRINTER_INFO = "printer_info"
