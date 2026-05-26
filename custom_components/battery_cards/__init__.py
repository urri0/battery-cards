"""Battery Cards integration."""

from __future__ import annotations

import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall

from .const import DOMAIN, SERVICE_RELOAD

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up Battery Cards services."""

    async def async_reload_service(call: ServiceCall) -> None:
        """Reload all Battery Cards entries."""
        entries = hass.config_entries.async_entries(DOMAIN)

        if not entries:
            _LOGGER.info("Battery Cards reload requested, but no entries exist")
            return

        await asyncio.gather(
            *(hass.config_entries.async_reload(entry.entry_id) for entry in entries)
        )

        _LOGGER.info("Battery Cards reloaded %s entries", len(entries))

    if not hass.services.has_service(DOMAIN, SERVICE_RELOAD):
        hass.services.async_register(DOMAIN, SERVICE_RELOAD, async_reload_service)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Battery Cards from a config entry."""
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Battery Cards config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload entry when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)