"""Config flow for IPP Advanced."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from pyipp import IPP, IPPConnectionError, IPPConnectionUpgradeRequired, IPPError

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL, CONF_VERIFY_SSL
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_BASE_PATH, DEFAULT_BASE_PATH, DEFAULT_PORT, DEFAULT_TLS, DEFAULT_VERIFY_SSL, DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_BASE_PATH, default=DEFAULT_BASE_PATH): str,
        vol.Optional(CONF_SSL, default=DEFAULT_TLS): bool,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): bool,
    }
)


class IPPAdvancedConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for IPP Advanced."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
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
                errors["base"] = "connection_upgrade"
            except (IPPConnectionError, IPPError, OSError):
                errors["base"] = "cannot_connect"
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
