"""Config flow for Battery Cards."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.util import slugify

from .const import (
    BATTERY_MODE_OPTIONS,
    BATTERY_RULE_OPTIONS,
    CONF_MODE,
    CONF_OBJECT_ID,
    CONF_RULE,
    CONF_SOURCE_ENTITY,
    DOMAIN,
    MODE_PHYSICAL,
    RULE_SOURCE_UNAVAILABLE,
)

_LOGGER = logging.getLogger(__name__)


def _mode_selector() -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[
                {"value": "physical", "label": "Physical"},
                {"value": "virtual", "label": "Virtual"},
            ],
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


def _rule_selector() -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[
                {
                    "value": "source_unavailable",
                    "label": "Source unavailable → 0%",
                },
                {
                    "value": "temperature_zero",
                    "label": "Temperature 0°C / unavailable → 0%",
                },
            ],
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


def _source_entity_selector() -> selector.EntitySelector:
    return selector.EntitySelector(
        selector.EntitySelectorConfig(
            domain="sensor",
        )
    )


class BatteryCardsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Battery Cards."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> BatteryCardsOptionsFlow:
        """Create the options flow."""
        return BatteryCardsOptionsFlow(config_entry)

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            name = str(user_input[CONF_NAME]).strip()
            object_id_raw = str(user_input.get(CONF_OBJECT_ID) or "").strip()
            object_id = slugify(object_id_raw or name)

            if not object_id:
                errors["base"] = "invalid_object_id"
            else:
                await self.async_set_unique_id(object_id)
                self._abort_if_unique_id_configured()

                data = {
                    CONF_NAME: name,
                    CONF_OBJECT_ID: object_id,
                    CONF_MODE: user_input[CONF_MODE],
                    CONF_SOURCE_ENTITY: user_input[CONF_SOURCE_ENTITY],
                    CONF_RULE: user_input.get(CONF_RULE, RULE_SOURCE_UNAVAILABLE),
                }

                return self.async_create_entry(
                    title=name,
                    data=data,
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): str,
                vol.Optional(CONF_OBJECT_ID): str,
                vol.Required(CONF_MODE, default=MODE_PHYSICAL): _mode_selector(),
                vol.Required(CONF_SOURCE_ENTITY): _source_entity_selector(),
                vol.Optional(
                    CONF_RULE,
                    default=RULE_SOURCE_UNAVAILABLE,
                ): _rule_selector(),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )


class BatteryCardsOptionsFlow(config_entries.OptionsFlow):
    """Handle Battery Cards options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Manage options."""
        current = {
            **self.config_entry.data,
            **self.config_entry.options,
        }

        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    CONF_NAME: str(user_input[CONF_NAME]).strip(),
                    CONF_MODE: user_input[CONF_MODE],
                    CONF_SOURCE_ENTITY: user_input[CONF_SOURCE_ENTITY],
                    CONF_RULE: user_input.get(CONF_RULE, RULE_SOURCE_UNAVAILABLE),
                },
            )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_NAME,
                    default=current.get(CONF_NAME, ""),
                ): str,
                vol.Required(
                    CONF_MODE,
                    default=current.get(CONF_MODE, MODE_PHYSICAL),
                ): _mode_selector(),
                vol.Required(
                    CONF_SOURCE_ENTITY,
                    default=current.get(CONF_SOURCE_ENTITY, ""),
                ): _source_entity_selector(),
                vol.Optional(
                    CONF_RULE,
                    default=current.get(CONF_RULE, RULE_SOURCE_UNAVAILABLE),
                ): _rule_selector(),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
        )