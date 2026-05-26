"""Constants for Battery Cards."""

from __future__ import annotations

DOMAIN = "battery_cards"
VERSION = "0.2.0"

CONF_OBJECT_ID = "object_id"
CONF_MODE = "mode"
CONF_SOURCE_ENTITY = "source_entity"
CONF_RULE = "rule"
CONF_MIN_VOLTAGE = "min_voltage"
CONF_BATTERY_TYPE_HINT = "battery_type_hint"

MODE_PHYSICAL = "physical"
MODE_VIRTUAL = "virtual"

RULE_PHYSICAL_PERCENT = "physical_percent"
RULE_SOURCE_UNAVAILABLE = "source_unavailable"
RULE_TEMPERATURE_ZERO = "temperature_zero"
RULE_BATTERY_LOW_BINARY = "battery_low_binary"
RULE_VOLTAGE_THRESHOLD = "voltage_threshold"

SERVICE_RELOAD = "reload"

DEFAULT_MIN_VOLTAGE = 2.7
DEFAULT_BATTERY_TYPE_HINT = "custom"

BATTERY_MODE_OPTIONS = [
    MODE_PHYSICAL,
    MODE_VIRTUAL,
]

BATTERY_RULE_OPTIONS = [
    RULE_SOURCE_UNAVAILABLE,
    RULE_TEMPERATURE_ZERO,
    RULE_BATTERY_LOW_BINARY,
    RULE_VOLTAGE_THRESHOLD,
]

BATTERY_TYPE_HINT_OPTIONS = [
    "cr_3v_coin",
    "aa_aaa_alkaline_1x",
    "aa_aaa_alkaline_2x",
    "aa_aaa_nimh_1x",
    "aa_aaa_nimh_2x",
    "custom",
]

BAD_STATES = {"unknown", "unavailable", "none", "null", ""}

LOW_BINARY_ON_STATES = {
    "on",
    "true",
    "low",
    "problem",
    "1",
    "yes",
    "detected",
    "active",
}

LOW_BINARY_OFF_STATES = {
    "off",
    "false",
    "normal",
    "clear",
    "0",
    "no",
    "ok",
    "inactive",
}