"""Sensor platform for Battery Cards."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import re
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, PERCENTAGE
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import dt as dt_util

try:
    from homeassistant.helpers import floor_registry as fr
except ImportError:
    fr = None

from .const import (
    BAD_STATES,
    CONF_BATTERY_TYPE_HINT,
    CONF_MIN_VOLTAGE,
    CONF_MODE,
    CONF_OBJECT_ID,
    CONF_RULE,
    CONF_SOURCE_ENTITY,
    DEFAULT_BATTERY_TYPE_HINT,
    DEFAULT_MIN_VOLTAGE,
    DOMAIN,
    LOW_BINARY_OFF_STATES,
    LOW_BINARY_ON_STATES,
    MODE_PHYSICAL,
    MODE_VIRTUAL,
    RULE_BATTERY_LOW_BINARY,
    RULE_PHYSICAL_PERCENT,
    RULE_SOURCE_UNAVAILABLE,
    RULE_TEMPERATURE_ZERO,
    RULE_VOLTAGE_THRESHOLD,
    VERSION,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class BatteryNotesEntities:
    """Battery Notes sibling entities for this card."""

    battery_type: str
    battery_last_replaced: str
    battery_replaced_button: str


@dataclass
class EntityLocation:
    """Resolved HA location info."""

    area: str
    floor: str
    location: str
    location_icon: str
    location_display: str
    resolved_from: str


@dataclass
class VoltageInfo:
    """Parsed voltage info."""

    voltage: float | None
    raw_value: str | None
    unit: str | None
    unit_detected: str


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Battery Cards sensors."""
    async_add_entities([BatteryCardSensor(hass, entry)], True)


class BatteryCardSensor(SensorEntity):
    """Battery Card sensor."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_has_entity_name = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize Battery Card sensor."""
        self.hass = hass
        self._entry = entry

        cfg = self._cfg
        self._object_id = cfg[CONF_OBJECT_ID]

        # Важно: entity_id жёстко задаётся от object_id.
        # object_id: emastiff -> sensor.emastiff_battery_card
        self.entity_id = f"sensor.{self._object_id}_battery_card"

        self._attr_unique_id = f"{self._object_id}_battery_card"
        self._attr_suggested_object_id = f"{self._object_id}_battery_card"
        self._attr_name = cfg.get(CONF_NAME, self._object_id)

    @property
    def _cfg(self) -> dict[str, Any]:
        """Return merged config data and options."""
        return {
            **self._entry.data,
            **self._entry.options,
        }

    @property
    def source_entity(self) -> str:
        """Return source entity."""
        return str(self._cfg.get(CONF_SOURCE_ENTITY, "")).strip()

    @property
    def battery_mode(self) -> str:
        """Return battery mode."""
        return self._cfg.get(CONF_MODE, MODE_PHYSICAL)

    @property
    def battery_rule(self) -> str:
        """Return battery rule."""
        if self.battery_mode == MODE_PHYSICAL:
            return RULE_PHYSICAL_PERCENT

        return self._cfg.get(CONF_RULE, RULE_SOURCE_UNAVAILABLE)

    @property
    def min_voltage(self) -> float:
        """Return voltage threshold in volts."""
        return _to_float(self._cfg.get(CONF_MIN_VOLTAGE, DEFAULT_MIN_VOLTAGE)) or DEFAULT_MIN_VOLTAGE

    @property
    def battery_type_hint(self) -> str:
        """Return battery type hint."""
        return str(self._cfg.get(CONF_BATTERY_TYPE_HINT, DEFAULT_BATTERY_TYPE_HINT))

    @property
    def name(self) -> str | None:
        """Return display name."""
        return self._cfg.get(CONF_NAME, self._object_id)

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._object_id)},
            "name": self.name,
            "manufacturer": "Battery Cards",
            "model": self.battery_mode,
            "sw_version": VERSION,
        }

    async def async_added_to_hass(self) -> None:
        """Track source and Battery Notes sibling entities."""
        notes = self._battery_notes_entities()

        tracked_entities = [
            self.source_entity,
            notes.battery_type,
            notes.battery_last_replaced,
            notes.battery_replaced_button,
        ]

        tracked_entities = [entity_id for entity_id in tracked_entities if entity_id]

        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                tracked_entities,
                self._handle_tracked_state_change,
            )
        )

    @callback
    def _handle_tracked_state_change(self, event: Event) -> None:
        """Handle tracked state changes."""
        self.async_write_ha_state()

    @property
    def native_value(self) -> int:
        """Return battery level."""
        if not self.source_entity:
            return 0

        state_obj = self.hass.states.get(self.source_entity)

        if self.battery_mode == MODE_PHYSICAL:
            return self._physical_value(state_obj)

        if self.battery_mode == MODE_VIRTUAL:
            return self._virtual_value(state_obj)

        return 0

    def _physical_value(self, state_obj) -> int:
        """Return physical percent battery value."""
        if state_obj is None:
            return 0

        raw = str(state_obj.state).strip().lower()
        if raw in BAD_STATES:
            return 0

        value = _to_float(raw)
        if value is None:
            return 0

        return _clamp_percent(round(value))

    def _virtual_value(self, state_obj) -> int:
        """Return virtual battery value."""
        rule = self.battery_rule

        if rule == RULE_SOURCE_UNAVAILABLE:
            return self._source_unavailable_value(state_obj)

        if rule == RULE_TEMPERATURE_ZERO:
            return self._temperature_zero_value(state_obj)

        if rule == RULE_BATTERY_LOW_BINARY:
            return self._battery_low_binary_value(state_obj)

        if rule == RULE_VOLTAGE_THRESHOLD:
            return self._voltage_threshold_value(state_obj)

        return self._source_unavailable_value(state_obj)

    def _source_unavailable_value(self, state_obj) -> int:
        """Return 100 when source is available, 0 when source is unavailable."""
        if state_obj is None:
            return 0

        raw = str(state_obj.state).strip().lower()
        if raw in BAD_STATES:
            return 0

        return 100

    def _temperature_zero_value(self, state_obj) -> int:
        """Return 0 when temperature is zero or source is unavailable."""
        if state_obj is None:
            return 0

        raw = str(state_obj.state).strip().lower()
        if raw in BAD_STATES:
            return 0

        value = _to_float(raw)
        if value is None:
            return 0

        if abs(value) < 0.001:
            return 0

        return 100

    def _battery_low_binary_value(self, state_obj) -> int:
        """Return 10 when low battery flag is active."""
        if state_obj is None:
            return 0

        raw = str(state_obj.state).strip().lower()
        if raw in BAD_STATES:
            return 0

        if raw in LOW_BINARY_ON_STATES:
            return 10

        if raw in LOW_BINARY_OFF_STATES:
            return 100

        value = _to_float(raw)
        if value is not None:
            if abs(value) < 0.001:
                return 100

            if abs(value - 1.0) < 0.001:
                return 10

            # Некорректное числовое значение для battery_low flag.
            # Например, пользователь случайно выбрал процентный sensor 87%.
            # Для dashboard лучше вернуть 0%, а причину показать в attributes.
            return 0

        return 0

    def _voltage_threshold_value(self, state_obj) -> int:
        """Return 10 when voltage is below threshold."""
        if state_obj is None:
            return 0

        raw = str(state_obj.state).strip().lower()
        if raw in BAD_STATES:
            return 0

        voltage_info = _voltage_info(state_obj)
        if voltage_info.voltage is None:
            return 0

        return 10 if voltage_info.voltage < self.min_voltage else 100

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        state_obj = self.hass.states.get(self.source_entity) if self.source_entity else None
        notes = self._battery_notes_entities()

        # Основная логика location:
        # 1) сначала берём location самой Battery Cards entity
        # 2) если у неё нет area/floor — fallback на source_entity
        location = _resolve_location_with_fallback(
            self.hass,
            primary_entity_id=self.entity_id,
            fallback_entity_id=self.source_entity,
        )

        source_only_location = _entity_location_info(
            self.hass,
            self.source_entity,
            resolved_from="source_entity",
        )

        source_state = state_obj.state if state_obj is not None else "missing"

        type_state = self.hass.states.get(notes.battery_type)
        date_state = self.hass.states.get(notes.battery_last_replaced)

        voltage_info = (
            _voltage_info(state_obj)
            if self.battery_rule == RULE_VOLTAGE_THRESHOLD
            else _not_applicable_voltage_info()
        )

        return {
            "battery_card": True,
            "battery_mode": self.battery_mode,
            "battery_rule": self.battery_rule,
            "battery_reason": self._battery_reason(state_obj),
            "source_entity": self.source_entity,
            "source_state": source_state,
            # Финальные location/area для карточки.
            "source_area": location.area,
            "source_floor": location.floor,
            "source_location": location.location,
            "source_location_icon": location.location_icon,
            "source_location_display": location.location_display,
            "source_location_resolved_from": location.resolved_from,
            # Диагностические атрибуты: что было у исходника.
            "raw_source_area": source_only_location.area,
            "raw_source_floor": source_only_location.floor,
            "raw_source_location": source_only_location.location,
            "source_friendly_name": (
                state_obj.attributes.get("friendly_name")
                if state_obj is not None
                else None
            ),
            "battery_type_entity": notes.battery_type,
            "battery_last_replaced_entity": notes.battery_last_replaced,
            "battery_replaced_button": notes.battery_replaced_button,
            "battery_type_and_quantity": _clean_state(
                type_state.state if type_state is not None else None
            ),
            "battery_last_replaced": _format_date(
                date_state.state if date_state is not None else None
            ),
            "voltage": voltage_info.voltage,
            "voltage_raw": voltage_info.raw_value,
            "voltage_unit": voltage_info.unit,
            "voltage_unit_detected": voltage_info.unit_detected,
            "min_voltage": self.min_voltage,
            "battery_type_hint": self.battery_type_hint,
        }

    def _battery_reason(self, state_obj) -> str:
        """Return battery reason."""
        if not self.source_entity:
            return "source_missing"

        if self.battery_mode == MODE_PHYSICAL:
            if state_obj is None:
                return "source_missing"

            raw = str(state_obj.state).strip().lower()
            if raw in BAD_STATES:
                return "source_unavailable"

            value = _to_float(raw)
            if value is None:
                return "source_not_numeric"

            return "source_percent"

        if self.battery_mode != MODE_VIRTUAL:
            return "unknown"

        rule = self.battery_rule

        if state_obj is None:
            return "source_missing"

        raw = str(state_obj.state).strip().lower()

        if raw in BAD_STATES:
            return "source_unavailable"

        if rule == RULE_SOURCE_UNAVAILABLE:
            return "ok"

        if rule == RULE_TEMPERATURE_ZERO:
            value = _to_float(raw)
            if value is None:
                return "source_not_numeric"
            if abs(value) < 0.001:
                return "temperature_zero"
            return "ok"

        if rule == RULE_BATTERY_LOW_BINARY:
            if raw in LOW_BINARY_ON_STATES:
                return "low_binary_on"
            if raw in LOW_BINARY_OFF_STATES:
                return "low_binary_off"

            value = _to_float(raw)
            if value is not None:
                if abs(value) < 0.001:
                    return "low_binary_off"
                if abs(value - 1.0) < 0.001:
                    return "low_binary_on"
                return "low_binary_invalid_numeric"

            return "low_binary_unknown_value"

        if rule == RULE_VOLTAGE_THRESHOLD:
            voltage_info = _voltage_info(state_obj)
            if voltage_info.voltage is None:
                return "voltage_not_numeric"
            if voltage_info.voltage < self.min_voltage:
                return "voltage_below_threshold"
            return "voltage_ok"

        return "unknown_rule"

    def _battery_notes_entities(self) -> BatteryNotesEntities:
        """Return Battery Notes sibling entities based on this entity_id."""
        entity_id = self.entity_id or f"sensor.{self._object_id}_battery_card"
        object_id = entity_id.split(".", 1)[1]

        return BatteryNotesEntities(
            battery_type=f"sensor.{object_id}_battery_type",
            battery_last_replaced=f"sensor.{object_id}_battery_last_replaced",
            battery_replaced_button=f"button.{object_id}_battery_replaced",
        )


def _to_float(value: Any) -> float | None:
    """Convert value to float.

    Supports values like:
    - 75
    - 75.5
    - 75,5
    - 75 %
    - 75%
    - 0,0
    - 2.95 V
    - 2950 mV
    """
    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    text = text.replace("%", "").replace(",", ".").strip()

    try:
        return float(text)
    except (TypeError, ValueError):
        pass

    match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    if match is None:
        return None

    try:
        return float(match.group(0))
    except (TypeError, ValueError):
        return None


def _not_applicable_voltage_info() -> VoltageInfo:
    """Return voltage info for non-voltage rules."""
    return VoltageInfo(
        voltage=None,
        raw_value=None,
        unit=None,
        unit_detected="not_applicable",
    )


def _voltage_info(state_obj) -> VoltageInfo:
    """Parse voltage from state object and return diagnostic info."""
    if state_obj is None:
        return VoltageInfo(
            voltage=None,
            raw_value="missing",
            unit="",
            unit_detected="missing",
        )

    raw_value = str(state_obj.state or "").strip()
    unit = str(state_obj.attributes.get("unit_of_measurement", "") or "").strip()

    value = _to_float(raw_value)
    if value is None:
        return VoltageInfo(
            voltage=None,
            raw_value=raw_value,
            unit=unit,
            unit_detected="not_numeric",
        )

    raw_lower = raw_value.lower()
    unit_lower = unit.lower()

    # Explicit mV in state or unit.
    if "mv" in raw_lower or unit_lower in {"mv", "millivolt", "millivolts"}:
        return VoltageInfo(
            voltage=value / 1000.0,
            raw_value=raw_value,
            unit=unit,
            unit_detected="mV",
        )

    # Explicit V in unit/state.
    if unit_lower in {"v", "volt", "volts"} or raw_lower.endswith("v"):
        return VoltageInfo(
            voltage=value,
            raw_value=raw_value,
            unit=unit,
            unit_detected="V",
        )

    # Heuristic:
    # Battery voltage cannot realistically be 2950 V, so large values are treated as mV.
    # This is diagnostic-visible via voltage_unit_detected=mV_auto.
    if value > 20:
        return VoltageInfo(
            voltage=value / 1000.0,
            raw_value=raw_value,
            unit=unit,
            unit_detected="mV_auto",
        )

    return VoltageInfo(
        voltage=value,
        raw_value=raw_value,
        unit=unit,
        unit_detected="V_auto",
    )


def _clamp_percent(value: int) -> int:
    """Clamp battery percentage."""
    return max(0, min(100, value))


def _clean_state(value: Any) -> str:
    """Clean HA state."""
    text = str(value or "").strip()

    if text.lower() in BAD_STATES:
        return "—"

    return text


def _format_date(value: Any) -> str:
    """Format date from Battery Notes."""
    text = _clean_state(value)

    if text == "—":
        return "—"

    parsed_datetime = dt_util.parse_datetime(text)
    if parsed_datetime is not None:
        return parsed_datetime.strftime("%d.%m.%y")

    parsed_date = dt_util.parse_date(text)
    if parsed_date is not None:
        return parsed_date.strftime("%d.%m.%y")

    return text


def _resolve_location_with_fallback(
    hass: HomeAssistant,
    primary_entity_id: str | None,
    fallback_entity_id: str | None,
) -> EntityLocation:
    """Resolve location using primary entity first, then fallback entity."""
    if primary_entity_id:
        primary = _entity_location_info(
            hass,
            primary_entity_id,
            resolved_from="battery_card_entity",
        )
        if primary.area != "—" or primary.location != "—":
            return primary

    if fallback_entity_id:
        fallback = _entity_location_info(
            hass,
            fallback_entity_id,
            resolved_from="source_entity",
        )
        if fallback.area != "—" or fallback.location != "—":
            return fallback

    return EntityLocation(
        area="—",
        floor="—",
        location="—",
        location_icon="",
        location_display="—",
        resolved_from="none",
    )


def _entity_location_info(
    hass: HomeAssistant,
    entity_id: str | None,
    resolved_from: str,
) -> EntityLocation:
    """Resolve entity area and HA floor/location."""
    if not entity_id:
        return EntityLocation(
            area="—",
            floor="—",
            location="—",
            location_icon="",
            location_display="—",
            resolved_from=resolved_from,
        )

    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    area_registry = ar.async_get(hass)

    registry_entry = entity_registry.async_get(entity_id)
    area_id = None

    if registry_entry is not None:
        # 1. Area directly assigned to entity.
        area_id = registry_entry.area_id

        # 2. Fallback to device area.
        if area_id is None and registry_entry.device_id is not None:
            device_entry = device_registry.async_get(registry_entry.device_id)
            if device_entry is not None:
                area_id = device_entry.area_id

    if area_id is None:
        return EntityLocation(
            area="—",
            floor="—",
            location="—",
            location_icon="",
            location_display="—",
            resolved_from=resolved_from,
        )

    area_entry = area_registry.async_get_area(area_id)

    if area_entry is None:
        return EntityLocation(
            area="—",
            floor="—",
            location="—",
            location_icon="",
            location_display="—",
            resolved_from=resolved_from,
        )

    area_name = area_entry.name
    floor_name = "—"

    floor_id = getattr(area_entry, "floor_id", None)

    if floor_id and fr is not None:
        floor_registry = fr.async_get(hass)
        floor_entry = floor_registry.async_get_floor(floor_id)

        if floor_entry is not None:
            floor_name = floor_entry.name

    location_name = floor_name
    location_icon = _location_icon(location_name)
    location_display = (
        f"{location_icon} {location_name}"
        if location_icon and location_name != "—"
        else location_name
    )

    return EntityLocation(
        area=area_name,
        floor=floor_name,
        location=location_name,
        location_icon=location_icon,
        location_display=location_display,
        resolved_from=resolved_from,
    )


def _location_icon(location_name: str) -> str:
    """Return icon for HA floor/location."""
    name = str(location_name or "").strip().lower()

    # Гибкое определение локации.
    # Сделано по имени floor/location, а не по entity_id,
    # чтобы интеграция не зависела от конкретной инсталляции.
    home_keywords = {
        "дом",
        "home",
        "apartment",
        "flat",
        "квартира",
    }

    cottage_keywords = {
        "дача",
        "chalet",
        "cottage",
        "country",
        "country house",
        "country_house",
        "загород",
    }

    if any(keyword in name for keyword in home_keywords):
        return "🏢"

    if any(keyword in name for keyword in cottage_keywords):
        return "🏠"

    return ""