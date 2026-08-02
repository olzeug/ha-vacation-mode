"""Shared entity base for Vacation Mode."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import VacationModeCoordinator
from .models import VacationModeData


def location_label(data: VacationModeData) -> str:
    """Shortest name identifying where the traveller currently is."""
    if data.place is not None:
        for candidate in (data.place.city, data.place.state, data.place.country):
            if candidate:
                return candidate
    if data.weather is not None and data.weather.timezone:
        # "Asia/Bangkok" -> "Bangkok"
        return data.weather.timezone.rsplit("/", 1)[-1].replace("_", " ")
    return ""


class VacationModeEntity(CoordinatorEntity[VacationModeCoordinator]):
    """Base entity tying every platform to the shared device and coordinator."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: VacationModeCoordinator, key: str) -> None:
        """Initialise the entity."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer=MANUFACTURER,
            entry_type=DeviceEntryType.SERVICE,
        )
