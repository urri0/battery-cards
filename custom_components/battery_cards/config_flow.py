"""Config flow for Battery Cards."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.util import slugify

from .const import (
    CONF_BATTERY_TYPE_HINT,
    CONF_MIN_VOLTAGE,
    CONF_MODE,
    CONF_OBJECT_ID,
    CONF_RULE,
    CONF_SOURCE_ENTITY,
    DEFAULT_BATTERY_TYPE_HINT,
    DEFAULT_MIN_VOLTAGE,
    DOMAIN,
    MODE_PHYSICAL,
    MODE_VIRTUAL,
    RULE_BATTERY_LOW_BINARY,
    RULE_PHYSICAL_PERCENT,
    RULE_SOURCE_UNAVAILABLE,
    RULE_TEMPERATURE_ZERO,
    RULE_VOLTAGE_THRESHOLD,
)


def _mode_selector() -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[
                {
                    "value": MODE_PHYSICAL,
                    "label": "Обычная батарейка — источник уже отдаёт %",
                },
                {
                    "value": MODE_VIRTUAL,
                    "label": "Вычисляемая батарейка — процента нет, считаем по признаку",
                },
            ],
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


def _virtual_rule_selector() -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[
                {
                    "value": RULE_SOURCE_UNAVAILABLE,
                    "label": "Доступно = 100%, недоступно = 0%",
                },
                {
                    "value": RULE_TEMPERATURE_ZERO,
                    "label": "0°C или недоступно = 0%, иначе = 100%",
                },
                {
                    "value": RULE_BATTERY_LOW_BINARY,
                    "label": "Battery Low: low/on = 10%, normal/off = 100%, недоступно = 0%",
                },
                {
                    "value": RULE_VOLTAGE_THRESHOLD,
                    "label": "Напряжение: ниже minV = 10%, выше = 100%, недоступно = 0%",
                },
            ],
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


def _battery_type_hint_selector() -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[
                {
                    "value": "cr_3v_coin",
                    "label": "CR2032 / CR2450 / 3V coin — стартовый minV около 2.7 V",
                },
                {
                    "value": "aa_aaa_alkaline_1x",
                    "label": "1× AA/AAA alkaline — стартовый minV около 1.1 V",
                },
                {
                    "value": "aa_aaa_alkaline_2x",
                    "label": "2× AA/AAA alkaline — стартовый minV около 2.2 V",
                },
                {
                    "value": "aa_aaa_nimh_1x",
                    "label": "1× AA/AAA NiMH — стартовый minV около 1.0 V",
                },
                {
                    "value": "aa_aaa_nimh_2x",
                    "label": "2× AA/AAA NiMH — стартовый minV около 2.0 V",
                },
                {
                    "value": "custom",
                    "label": "Custom — порог задаю вручную",
                },
            ],
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


def _physical_source_entity_selector() -> selector.EntitySelector:
    return selector.EntitySelector(
        selector.EntitySelectorConfig(
            domain="sensor",
        )
    )


def _source_unavailable_entity_selector() -> selector.EntitySelector:
    return selector.EntitySelector(
        selector.EntitySelectorConfig(
            domain=["sensor", "binary_sensor"],
        )
    )


def _temperature_zero_entity_selector() -> selector.EntitySelector:
    return selector.EntitySelector(
        selector.EntitySelectorConfig(
            domain="sensor",
        )
    )


def _battery_low_binary_entity_selector() -> selector.EntitySelector:
    return selector.EntitySelector(
        selector.EntitySelectorConfig(
            domain=["binary_sensor", "sensor"],
        )
    )


def _voltage_entity_selector() -> selector.EntitySelector:
    return selector.EntitySelector(
        selector.EntitySelectorConfig(
            domain="sensor",
        )
    )


def _virtual_source_entity_selector_for_rule(rule: str) -> selector.EntitySelector:
    if rule == RULE_TEMPERATURE_ZERO:
        return _temperature_zero_entity_selector()

    if rule == RULE_BATTERY_LOW_BINARY:
        return _battery_low_binary_entity_selector()

    if rule == RULE_VOLTAGE_THRESHOLD:
        return _voltage_entity_selector()

    return _source_unavailable_entity_selector()


def _allowed_domains_for_rule(rule: str) -> set[str]:
    if rule == RULE_TEMPERATURE_ZERO:
        return {"sensor"}

    if rule == RULE_BATTERY_LOW_BINARY:
        return {"sensor", "binary_sensor"}

    if rule == RULE_VOLTAGE_THRESHOLD:
        return {"sensor"}

    return {"sensor", "binary_sensor"}


def _entity_domain(entity_id: str | None) -> str:
    text = str(entity_id or "").strip()

    if "." not in text:
        return ""

    return text.split(".", 1)[0]


def _entity_schema_field(
    entity_selector: selector.EntitySelector,
    default_value: str | None,
    allowed_domains: set[str],
) -> tuple[Any, Any]:
    """Return entity selector schema field.

    Empty or domain-invalid defaults can break some HA options-flow forms,
    so default is used only when it is a real compatible entity_id.
    """
    default_value = str(default_value or "").strip()

    if default_value and _entity_domain(default_value) in allowed_domains:
        return (
            vol.Required(CONF_SOURCE_ENTITY, default=default_value),
            entity_selector,
        )

    return (
        vol.Required(CONF_SOURCE_ENTITY),
        entity_selector,
    )


def _suggest_min_voltage(hint: str) -> float:
    if hint == "cr_3v_coin":
        return 2.7
    if hint == "aa_aaa_alkaline_1x":
        return 1.1
    if hint == "aa_aaa_alkaline_2x":
        return 2.2
    if hint == "aa_aaa_nimh_1x":
        return 1.0
    if hint == "aa_aaa_nimh_2x":
        return 2.0
    return DEFAULT_MIN_VOLTAGE


def _float_default(value: Any, fallback: float = DEFAULT_MIN_VOLTAGE) -> float:
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return fallback


class BatteryCardsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Battery Cards."""

    VERSION = 1

    def __init__(self) -> None:
        self._flow_data: dict[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "BatteryCardsOptionsFlow":
        """Create the options flow."""
        return BatteryCardsOptionsFlow(config_entry)

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            name = str(user_input[CONF_NAME]).strip()
            object_id_raw = str(user_input.get(CONF_OBJECT_ID) or "").strip()
            object_id = slugify(object_id_raw or name)
            mode = user_input[CONF_MODE]

            if not object_id:
                errors["base"] = "invalid_object_id"
            else:
                await self.async_set_unique_id(object_id)
                self._abort_if_unique_id_configured()

                self._flow_data = {
                    CONF_NAME: name,
                    CONF_OBJECT_ID: object_id,
                    CONF_MODE: mode,
                }

                if mode == MODE_PHYSICAL:
                    return await self.async_step_physical()

                return await self.async_step_virtual_rule()

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): str,
                vol.Optional(CONF_OBJECT_ID): str,
                vol.Required(CONF_MODE, default=MODE_PHYSICAL): _mode_selector(),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "hint": "Обычная батарейка копирует процент из sensor. Вычисляемая батарейка создаёт 0/10/100% по выбранному признаку.",
            },
        )

    async def async_step_physical(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Configure physical percent battery."""
        if user_input is not None:
            data = {
                **self._flow_data,
                CONF_SOURCE_ENTITY: user_input[CONF_SOURCE_ENTITY],
                CONF_RULE: RULE_PHYSICAL_PERCENT,
                CONF_MIN_VOLTAGE: DEFAULT_MIN_VOLTAGE,
                CONF_BATTERY_TYPE_HINT: DEFAULT_BATTERY_TYPE_HINT,
            }

            return self.async_create_entry(
                title=data[CONF_NAME],
                data=data,
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_SOURCE_ENTITY): _physical_source_entity_selector(),
            }
        )

        return self.async_show_form(
            step_id="physical",
            data_schema=schema,
            description_placeholders={
                "description": "Выбери sensor, который уже отдаёт процент батареи 0–100%. Если источник станет unavailable/unknown/missing, Battery Cards покажет 0%, чтобы dashboard подсветил проблему.",
            },
        )

    async def async_step_virtual_rule(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Choose virtual battery rule."""
        if user_input is not None:
            self._flow_data[CONF_RULE] = user_input[CONF_RULE]
            return await self.async_step_virtual_source()

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_RULE,
                    default=RULE_SOURCE_UNAVAILABLE,
                ): _virtual_rule_selector(),
            }
        )

        return self.async_show_form(
            step_id="virtual_rule",
            data_schema=schema,
            description_placeholders={
                "description": "Выбери, по какому признаку Battery Cards будет делать итоговую батарейку 0/10/100%. Это нужно для устройств, которые сами не отдают процент батареи.",
            },
        )

    async def async_step_virtual_source(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Configure virtual battery source."""
        rule = self._flow_data.get(CONF_RULE, RULE_SOURCE_UNAVAILABLE)

        if user_input is not None:
            hint = user_input.get(CONF_BATTERY_TYPE_HINT, DEFAULT_BATTERY_TYPE_HINT)
            min_voltage = user_input.get(CONF_MIN_VOLTAGE)

            if rule == RULE_VOLTAGE_THRESHOLD and min_voltage in (None, ""):
                min_voltage = _suggest_min_voltage(hint)

            data = {
                **self._flow_data,
                CONF_SOURCE_ENTITY: user_input[CONF_SOURCE_ENTITY],
                CONF_MIN_VOLTAGE: _float_default(min_voltage, DEFAULT_MIN_VOLTAGE),
                CONF_BATTERY_TYPE_HINT: hint,
            }

            return self.async_create_entry(
                title=data[CONF_NAME],
                data=data,
            )

        schema_dict: dict[Any, Any] = {
            vol.Required(CONF_SOURCE_ENTITY): _virtual_source_entity_selector_for_rule(rule),
        }

        if rule == RULE_VOLTAGE_THRESHOLD:
            schema_dict[
                vol.Required(
                    CONF_BATTERY_TYPE_HINT,
                    default=DEFAULT_BATTERY_TYPE_HINT,
                )
            ] = _battery_type_hint_selector()

            schema_dict[
                vol.Optional(
                    CONF_MIN_VOLTAGE,
                    default=DEFAULT_MIN_VOLTAGE,
                )
            ] = selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0.1,
                    max=10.0,
                    step=0.01,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="V",
                )
            )

        schema = vol.Schema(schema_dict)

        return self.async_show_form(
            step_id="virtual_source",
            data_schema=schema,
            description_placeholders={
                "description": _description_for_rule(rule),
            },
        )


class BatteryCardsOptionsFlow(config_entries.OptionsFlow):
    """Handle Battery Cards options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        # Не используем self.config_entry — в некоторых версиях HA
        # это внутреннее свойство OptionsFlow.
        self._config_entry = config_entry
        self._options_data: dict[str, Any] = {}

    @property
    def _current(self) -> dict[str, Any]:
        return {
            **self._config_entry.data,
            **self._config_entry.options,
        }

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Start options flow."""
        current = self._current

        if user_input is not None:
            self._options_data = {
                CONF_NAME: str(user_input[CONF_NAME]).strip(),
                CONF_MODE: user_input[CONF_MODE],
            }

            if user_input[CONF_MODE] == MODE_PHYSICAL:
                return await self.async_step_physical()

            return await self.async_step_virtual_rule()

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
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            description_placeholders={
                "description": "Object ID не меняется после создания, чтобы entity_id и связь с Battery Notes не ломались.",
            },
        )

    async def async_step_physical(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Edit physical battery options."""
        current = self._current

        if user_input is not None:
            data = {
                **self._options_data,
                CONF_SOURCE_ENTITY: user_input[CONF_SOURCE_ENTITY],
                CONF_RULE: RULE_PHYSICAL_PERCENT,
                CONF_MIN_VOLTAGE: current.get(CONF_MIN_VOLTAGE, DEFAULT_MIN_VOLTAGE),
                CONF_BATTERY_TYPE_HINT: current.get(
                    CONF_BATTERY_TYPE_HINT,
                    DEFAULT_BATTERY_TYPE_HINT,
                ),
            }
            return self.async_create_entry(title="", data=data)

        entity_key, entity_value = _entity_schema_field(
            _physical_source_entity_selector(),
            current.get(CONF_SOURCE_ENTITY, ""),
            {"sensor"},
        )

        schema = vol.Schema(
            {
                entity_key: entity_value,
            }
        )

        return self.async_show_form(
            step_id="physical",
            data_schema=schema,
            description_placeholders={
                "description": "Обычная батарейка: выбери sensor, который уже отдаёт процент 0–100%. Если источник недоступен — Battery Cards покажет 0%.",
            },
        )

    async def async_step_virtual_rule(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Edit virtual battery rule."""
        current = self._current

        if user_input is not None:
            self._options_data[CONF_RULE] = user_input[CONF_RULE]
            return await self.async_step_virtual_source()

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_RULE,
                    default=current.get(CONF_RULE, RULE_SOURCE_UNAVAILABLE),
                ): _virtual_rule_selector(),
            }
        )

        return self.async_show_form(
            step_id="virtual_rule",
            data_schema=schema,
            description_placeholders={
                "description": "Выбери правило, по которому Battery Cards будет вычислять 0/10/100%.",
            },
        )

    async def async_step_virtual_source(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Edit virtual battery source."""
        current = self._current
        rule = self._options_data.get(
            CONF_RULE,
            current.get(CONF_RULE, RULE_SOURCE_UNAVAILABLE),
        )

        if user_input is not None:
            hint = user_input.get(
                CONF_BATTERY_TYPE_HINT,
                current.get(CONF_BATTERY_TYPE_HINT, DEFAULT_BATTERY_TYPE_HINT),
            )
            min_voltage = user_input.get(
                CONF_MIN_VOLTAGE,
                current.get(CONF_MIN_VOLTAGE, DEFAULT_MIN_VOLTAGE),
            )

            if rule == RULE_VOLTAGE_THRESHOLD and min_voltage in (None, ""):
                min_voltage = _suggest_min_voltage(hint)

            data = {
                **self._options_data,
                CONF_SOURCE_ENTITY: user_input[CONF_SOURCE_ENTITY],
                CONF_MIN_VOLTAGE: _float_default(min_voltage, DEFAULT_MIN_VOLTAGE),
                CONF_BATTERY_TYPE_HINT: hint,
            }

            return self.async_create_entry(title="", data=data)

        entity_key, entity_value = _entity_schema_field(
            _virtual_source_entity_selector_for_rule(rule),
            current.get(CONF_SOURCE_ENTITY, ""),
            _allowed_domains_for_rule(rule),
        )

        schema_dict: dict[Any, Any] = {
            entity_key: entity_value,
        }

        if rule == RULE_VOLTAGE_THRESHOLD:
            schema_dict[
                vol.Required(
                    CONF_BATTERY_TYPE_HINT,
                    default=current.get(CONF_BATTERY_TYPE_HINT, DEFAULT_BATTERY_TYPE_HINT),
                )
            ] = _battery_type_hint_selector()

            schema_dict[
                vol.Optional(
                    CONF_MIN_VOLTAGE,
                    default=_float_default(
                        current.get(CONF_MIN_VOLTAGE, DEFAULT_MIN_VOLTAGE),
                        DEFAULT_MIN_VOLTAGE,
                    ),
                )
            ] = selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0.1,
                    max=10.0,
                    step=0.01,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="V",
                )
            )

        schema = vol.Schema(schema_dict)

        return self.async_show_form(
            step_id="virtual_source",
            data_schema=schema,
            description_placeholders={
                "description": _description_for_rule(rule),
            },
        )


def _description_for_rule(rule: str) -> str:
    if rule == RULE_SOURCE_UNAVAILABLE:
        return (
            "Источник живости устройства. Если выбранная сущность доступна — будет 100%. "
            "Если unavailable/unknown/missing — будет 0%."
        )

    if rule == RULE_TEMPERATURE_ZERO:
        return (
            "Температурный sensor. Если температура 0°C или сущность недоступна — будет 0%. "
            "Иначе — 100%."
        )

    if rule == RULE_BATTERY_LOW_BINARY:
        return (
            "Binary sensor или sensor с флагом low battery. "
            "on/true/low/problem/1 → 10%. "
            "off/false/normal/clear/0 → 100%. "
            "unavailable/unknown/missing → 0%. "
            "Если случайно выбрать обычный процентный sensor, Battery Cards покажет 0% и причину low_binary_invalid_numeric."
        )

    if rule == RULE_VOLTAGE_THRESHOLD:
        return (
            "Sensor напряжения батареи. Понимает V и mV: 2.95 V или 2950 mV. "
            "Ниже minV → 10%. Выше или равно minV → 100%. "
            "unavailable/unknown/missing → 0%. "
            "Подсказка minV — стартовая, реальный порог зависит от устройства и химии батарейки."
        )

    return "Выбери исходную сущность."