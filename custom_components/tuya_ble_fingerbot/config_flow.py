from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_DEVICE_ID,
    CONF_INCLUDE_MOTION,
    CONF_LOCAL_KEY,
    CONF_MAC,
    CONF_PRODUCT_ID,
    CONF_PRODUCT_NAME,
    CONF_PROFILE,
    CONF_TIMEOUT,
    CONF_UUID,
    DEFAULT_NAME,
    DEFAULT_TIMEOUT,
    DOMAIN,
)
from .fingerbot import PROFILES, get_profile


def _normalize_mac(value: str) -> str:
    return value.strip().upper()


class TuyaBleFingerbotConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Tuya BLE Fingerbot config flow."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            user_input[CONF_MAC] = _normalize_mac(user_input[CONF_MAC])
            product_id = user_input.get(CONF_PRODUCT_ID) or None
            try:
                profile = get_profile(user_input[CONF_PROFILE], product_id)
            except Exception:
                errors["base"] = "invalid_profile"
            else:
                user_input[CONF_PROFILE] = profile.name
                await self.async_set_unique_id(user_input[CONF_DEVICE_ID])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=user_input,
                )

        defaults = user_input or {}
        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_NAME,
                    default=defaults.get(CONF_NAME, DEFAULT_NAME),
                ): str,
                vol.Required(
                    CONF_MAC,
                    default=defaults.get(CONF_MAC, ""),
                ): str,
                vol.Required(
                    CONF_LOCAL_KEY,
                    default=defaults.get(CONF_LOCAL_KEY, ""),
                ): str,
                vol.Required(
                    CONF_UUID,
                    default=defaults.get(CONF_UUID, ""),
                ): str,
                vol.Required(
                    CONF_DEVICE_ID,
                    default=defaults.get(CONF_DEVICE_ID, ""),
                ): str,
                vol.Optional(
                    CONF_PRODUCT_ID,
                    default=defaults.get(CONF_PRODUCT_ID, ""),
                ): str,
                vol.Optional(
                    CONF_PRODUCT_NAME,
                    default=defaults.get(CONF_PRODUCT_NAME, DEFAULT_NAME),
                ): str,
                vol.Required(
                    CONF_PROFILE,
                    default=defaults.get(CONF_PROFILE, "auto"),
                ): vol.In(("auto", *PROFILES.keys())),
                vol.Required(
                    CONF_INCLUDE_MOTION,
                    default=defaults.get(CONF_INCLUDE_MOTION, True),
                ): bool,
                vol.Required(
                    CONF_TIMEOUT,
                    default=defaults.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
                ): float,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )
