"""Constants for Battery Cards."""

from __future__ import annotations

DOMAIN = "battery_cards"

PLATFORMS = ["sensor"]

CONF_OBJECT_ID = "object_id"
CONF_MODE = "mode"
CONF_SOURCE_ENTITY = "source_entity"
CONF_RULE = "rule"

MODE_PHYSICAL = "physical"
MODE_VIRTUAL = "virtual"

RULE_SOURCE_UNAVAILABLE = "source_unavailable"
RULE_TEMPERATURE_ZERO = "temperature_zero"

SERVICE_RELOAD = "reload"

BATTERY_MODE_OPTIONS = [
    MODE_PHYSICAL,
    MODE_VIRTUAL,
]

BATTERY_RULE_OPTIONS = [
    RULE_SOURCE_UNAVAILABLE,
    RULE_TEMPERATURE_ZERO,
]

BAD_STATES = {"unknown", "unavailable", "none", "null", ""}