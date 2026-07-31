"""Binary sensor platform for Vacation Mode."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    ADVISORY_NONE,
    MODULE_COUNTRY_INFO,
    MODULE_HOLIDAYS,
    MODULE_TRAVEL_ADVICE,
    TAP_WATER_SAFE,
)
from .coordinator import VacationModeConfigEntry, VacationModeCoordinator
from .entity import VacationModeEntity
from .models import VacationModeData


@dataclass(frozen=True, kw_only=True)
class VacationModeBinarySensorDescription(BinarySensorEntityDescription):
    """Describes a Vacation Mode binary sensor."""

    module: str
    value_fn: Callable[[VacationModeData], bool | None]
    attributes_fn: Callable[[VacationModeData], Mapping[str, Any] | None] | None = None
    available_fn: Callable[[VacationModeData], bool] = lambda data: True


BINARY_SENSORS: tuple[VacationModeBinarySensorDescription, ...] = (
    VacationModeBinarySensorDescription(
        key="holiday_today",
        translation_key="holiday_today",
        module=MODULE_HOLIDAYS,
        value_fn=lambda data: (
            data.holidays.today is not None if data.holidays else None
        ),
        available_fn=lambda data: data.holidays is not None,
        attributes_fn=lambda data: (
            {
                "name": data.holidays.today.local_name,
                "date": data.holidays.today.day.isoformat(),
                "nationwide": data.holidays.today.nationwide,
            }
            if data.holidays and data.holidays.today
            else None
        ),
    ),
    VacationModeBinarySensorDescription(
        key="tap_water",
        translation_key="tap_water",
        module=MODULE_COUNTRY_INFO,
        device_class=BinarySensorDeviceClass.SAFETY,
        value_fn=lambda data: (
            data.country.tap_water != TAP_WATER_SAFE if data.country else None
        ),
        available_fn=lambda data: data.country is not None,
        attributes_fn=lambda data: (
            {"rating": data.country.tap_water} if data.country else None
        ),
    ),
    VacationModeBinarySensorDescription(
        key="travel_warning",
        translation_key="travel_warning",
        module=MODULE_TRAVEL_ADVICE,
        device_class=BinarySensorDeviceClass.SAFETY,
        value_fn=lambda data: (
            data.advisory.level != ADVISORY_NONE if data.advisory else None
        ),
        available_fn=lambda data: data.advisory is not None,
        attributes_fn=lambda data: (
            {
                "level": data.advisory.level,
                "title": data.advisory.title,
                "summary": data.advisory.summary,
                "last_changes": data.advisory.last_changes,
                "url": data.advisory.url,
            }
            if data.advisory
            else None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VacationModeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensors for the enabled modules."""
    coordinator = entry.runtime_data
    modules = coordinator.modules
    async_add_entities(
        VacationModeBinarySensor(coordinator, description)
        for description in BINARY_SENSORS
        if modules.get(description.module)
    )


class VacationModeBinarySensor(VacationModeEntity, BinarySensorEntity):
    """A yes/no verdict derived from the coordinator data."""

    entity_description: VacationModeBinarySensorDescription

    def __init__(
        self,
        coordinator: VacationModeCoordinator,
        description: VacationModeBinarySensorDescription,
    ) -> None:
        """Initialise the binary sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        """Return whether the source of this sensor delivered data."""
        return super().available and self.entity_description.available_fn(
            self.coordinator.data
        )

    @property
    def is_on(self) -> bool | None:
        """Return the current state."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the additional details of this sensor."""
        if self.entity_description.attributes_fn is None:
            return None
        return self.entity_description.attributes_fn(self.coordinator.data)
