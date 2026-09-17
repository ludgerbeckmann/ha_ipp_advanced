"""Config flow for IPP Advanced."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from pyipp import IPP, IPPConnectionError, IPPConnectionUpgradeRequired, IPPError

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL, CONF_SSL, CONF_VERIFY_SSL
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_BASE_PATH,
    DEFAULT_BASE_PATH,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TLS,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_BASE_PATH, default=DEFAULT_BASE_PATH): str,
        vol.Optional(CONF_SSL, default=DEFAULT_TLS): bool,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): bool,
    }
)


async def _async_try_connect(user_input: dict[str, Any]):
    """Verbindung zum Drucker testen.

    Gibt bei Erfolg (Printer, None) zurück, sonst (None, <error-key>) -
    gemeinsame Logik für den initialen und den Reconfigure-Schritt.
    """
    ipp = IPP(
        host=user_input[CONF_HOST],
        port=user_input[CONF_PORT],
        base_path=user_input[CONF_BASE_PATH],
        tls=user_input[CONF_SSL],
        verify_ssl=user_input[CONF_VERIFY_SSL],
    )
    try:
        printer = await ipp.printer()
    except IPPConnectionUpgradeRequired:
        return None, "connection_upgrade"
    except (IPPConnectionError, IPPError, OSError):
        return None, "cannot_connect"
    return printer, None


class IPPAdvancedConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for IPP Advanced."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            printer, error = await _async_try_connect(user_input)
            if error is not None:
                errors["base"] = error
            else:
                await self.async_set_unique_id(printer.info.uuid or user_input[CONF_HOST])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=printer.info.name or user_input[CONF_HOST],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Erlaubt das nachträgliche Ändern von Host/Port/etc. eines
        bestehenden Eintrags, ohne ihn löschen und neu anlegen zu müssen."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            printer, error = await _async_try_connect(user_input)
            if error is not None:
                errors["base"] = error
            else:
                await self.async_set_unique_id(printer.info.uuid or user_input[CONF_HOST])
                self._abort_if_unique_id_mismatch()

                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    title=printer.info.name or user_input[CONF_HOST],
                    data=user_input,
                    reason="reconfigure_successful",
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, reconfigure_entry.data
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> IPPAdvancedOptionsFlow:
        """Options Flow für dieses Integration erstellen (Abfrageintervall)."""
        return IPPAdvancedOptionsFlow(config_entry)


class IPPAdvancedOptionsFlow(config_entries.OptionsFlow):
    """Options für einen bestehenden IPP-Advanced-Eintrag (Abfrageintervall)."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        # Explizite Zuweisung statt uns auf das seit HA 2024.12 automatisch
        # gesetzte self.config_entry zu verlassen - so funktioniert es auch
        # auf älteren, aber noch unterstützten HA-Versionen unverändert
        # (nur ein Deprecation-Log auf neueren, kein Fehler).
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Abfrageintervall verwalten."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                    )
                }
            ),
        )
