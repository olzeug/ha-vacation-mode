"""Actions exposed by the Vacation Mode integration."""

from __future__ import annotations

import asyncio
import logging

from homeassistant.const import ATTR_AREA_ID, ATTR_DEVICE_ID, ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
import voluptuous as vol

from .const import DOMAIN, SERVICE_REFRESH
from .coordinator import VacationModeConfigEntry

_LOGGER = logging.getLogger(__name__)

REFRESH_SCHEMA = vol.Schema(cv.TARGET_SERVICE_FIELDS)


def _targeted_entry_ids(hass: HomeAssistant, call: ServiceCall) -> set[str] | None:
    """Config entry ids the call points at, or None when it has no target."""
    devices = cv.ensure_list(call.data.get(ATTR_DEVICE_ID, []))
    entities = cv.ensure_list(call.data.get(ATTR_ENTITY_ID, []))
    areas = cv.ensure_list(call.data.get(ATTR_AREA_ID, []))
    if not devices and not entities and not areas:
        return None

    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    for area_id in areas:
        devices.extend(
            device.id for device in dr.async_entries_for_area(device_registry, area_id)
        )

    entry_ids: set[str] = set()
    for device_id in devices:
        if (device := device_registry.async_get(device_id)) is not None:
            entry_ids.update(device.config_entries)
    for entity_id in entities:
        entry = entity_registry.async_get(entity_id)
        if entry is not None and entry.config_entry_id is not None:
            entry_ids.add(entry.config_entry_id)
    return entry_ids


def _target_entries(
    hass: HomeAssistant, call: ServiceCall
) -> list[VacationModeConfigEntry]:
    """Resolve the loaded entries the call applies to."""
    loaded = hass.config_entries.async_loaded_entries(DOMAIN)
    if not loaded:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="no_loaded_entry"
        )

    if (entry_ids := _targeted_entry_ids(hass, call)) is None:
        return loaded

    entries = [entry for entry in loaded if entry.entry_id in entry_ids]
    if not entries:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="no_target_match"
        )
    return entries


async def _async_refresh(call: ServiceCall) -> None:
    """Refetch every source of the targeted entries, ignoring the caches."""
    entries = _target_entries(call.hass, call)
    _LOGGER.debug("Manual refresh of %d entries", len(entries))
    await asyncio.gather(
        *(entry.runtime_data.async_force_refresh() for entry in entries)
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the integration wide actions."""
    hass.services.async_register(
        DOMAIN, SERVICE_REFRESH, _async_refresh, schema=REFRESH_SCHEMA
    )
