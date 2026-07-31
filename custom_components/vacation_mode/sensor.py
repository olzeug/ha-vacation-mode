"""Sensor platform for Vacation Mode."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    PERCENTAGE,
    UnitOfLength,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from .const import (
    ADVISORY_LEVELS,
    MODULE_AIR_QUALITY,
    MODULE_COUNTRY_INFO,
    MODULE_CURRENCY,
    MODULE_EARTHQUAKES,
    MODULE_HOLIDAYS,
    MODULE_MARINE,
    MODULE_TRAVEL_ADVICE,
    MODULE_WEATHER,
)
from .coordinator import VacationModeConfigEntry, VacationModeCoordinator
from .entity import VacationModeEntity
from .models import VacationModeData

POLLEN_FIELDS = (
    "alder_pollen",
    "birch_pollen",
    "grass_pollen",
    "mugwort_pollen",
    "olive_pollen",
    "ragweed_pollen",
)
POLLEN_UNIT = "grains/m³"


@dataclass(frozen=True, kw_only=True)
class VacationModeSensorDescription(SensorEntityDescription):
    """Describes a Vacation Mode sensor."""

    module: str | None = None
    value_fn: Callable[[VacationModeData], StateType | datetime | date]
    attributes_fn: Callable[[VacationModeData], Mapping[str, Any] | None] | None = None
    available_fn: Callable[[VacationModeData], bool] = lambda data: True


def _current(data: VacationModeData, key: str) -> float | None:
    """Read a value from the current weather block."""
    if data.weather is None:
        return None
    return data.weather.current.get(key)


def _air(data: VacationModeData, key: str) -> float | None:
    """Read a value from the air quality block."""
    if data.air_quality is None:
        return None
    return data.air_quality.get(key)


def _marine(data: VacationModeData, key: str) -> float | None:
    """Read a value from the marine block."""
    if data.marine is None:
        return None
    return data.marine.get(key)


def _pollen_max(data: VacationModeData) -> float | None:
    """Highest pollen concentration across all measured types."""
    if data.air_quality is None:
        return None
    values = [
        value
        for field in POLLEN_FIELDS
        if (value := data.air_quality.get(field)) is not None
    ]
    return max(values) if values else None


def _time_difference(data: VacationModeData) -> float | None:
    """Hours between the destination and the Home Assistant timezone."""
    if data.weather is None:
        return None
    local = dt_util.now().utcoffset()
    if local is None:
        return None
    return round((data.weather.utc_offset_seconds - local.total_seconds()) / 3600, 2)


def _local_time_attributes(data: VacationModeData) -> Mapping[str, Any] | None:
    """Timezone details of the destination."""
    if data.weather is None:
        return None
    tzinfo = dt_util.get_time_zone(data.weather.timezone or "UTC")
    now = dt_util.utcnow().astimezone(tzinfo) if tzinfo else None
    return {
        "timezone": data.weather.timezone,
        "utc_offset_seconds": data.weather.utc_offset_seconds,
        "local_time": now.strftime("%H:%M") if now else None,
    }


def _next_holiday_attributes(data: VacationModeData) -> Mapping[str, Any] | None:
    """Date, weekday and remaining days of the upcoming public holiday."""
    if data.holidays is None or data.holidays.next is None:
        return None
    holiday = data.holidays.next
    return {
        "date": holiday.day.isoformat(),
        "days_until": (holiday.day - dt_util.now().date()).days,
        "name": holiday.name,
        "local_name": holiday.local_name,
        "nationwide": holiday.nationwide,
    }


def _forecast_max(data: VacationModeData) -> float | None:
    """Highest temperature forecast for today."""
    if data.weather is None or not data.weather.daily:
        return None
    return data.weather.daily[0].get("native_temperature")


SENSORS: tuple[VacationModeSensorDescription, ...] = (
    VacationModeSensorDescription(
        key="distance_home",
        translation_key="distance_home",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data: data.distance_home,
    ),
    VacationModeSensorDescription(
        key="country",
        translation_key="country",
        value_fn=lambda data: data.place.country if data.place else None,
        available_fn=lambda data: data.place is not None,
        attributes_fn=lambda data: (
            {
                "country_code": data.place.country_code,
                "city": data.place.city,
                "region": data.place.state,
                "location": data.place.display_name,
                "latitude": data.latitude,
                "longitude": data.longitude,
            }
            if data.place
            else None
        ),
    ),
    # -- weather ----------------------------------------------------------
    VacationModeSensorDescription(
        key="temperature",
        module=MODULE_WEATHER,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: _current(data, "temperature_2m"),
        available_fn=lambda data: data.weather is not None,
    ),
    VacationModeSensorDescription(
        key="apparent_temperature",
        translation_key="apparent_temperature",
        module=MODULE_WEATHER,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: _current(data, "apparent_temperature"),
        available_fn=lambda data: data.weather is not None,
    ),
    VacationModeSensorDescription(
        key="temperature_max",
        translation_key="temperature_max",
        module=MODULE_WEATHER,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=_forecast_max,
        available_fn=lambda data: data.weather is not None,
    ),
    VacationModeSensorDescription(
        key="humidity",
        module=MODULE_WEATHER,
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: _current(data, "relative_humidity_2m"),
        available_fn=lambda data: data.weather is not None,
    ),
    VacationModeSensorDescription(
        key="pressure",
        module=MODULE_WEATHER,
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        native_unit_of_measurement=UnitOfPressure.HPA,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _current(data, "pressure_msl"),
        available_fn=lambda data: data.weather is not None,
    ),
    VacationModeSensorDescription(
        key="wind_speed",
        module=MODULE_WEATHER,
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data: _current(data, "wind_speed_10m"),
        available_fn=lambda data: data.weather is not None,
    ),
    VacationModeSensorDescription(
        key="precipitation",
        module=MODULE_WEATHER,
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: _current(data, "precipitation"),
        available_fn=lambda data: data.weather is not None,
    ),
    VacationModeSensorDescription(
        key="uv_index",
        translation_key="uv_index",
        module=MODULE_WEATHER,
        native_unit_of_measurement="UV index",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: _current(data, "uv_index"),
        available_fn=lambda data: data.weather is not None,
    ),
    VacationModeSensorDescription(
        key="sunrise",
        translation_key="sunrise",
        module=MODULE_WEATHER,
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.weather.sunrise if data.weather else None,
        available_fn=lambda data: data.weather is not None,
    ),
    VacationModeSensorDescription(
        key="sunset",
        translation_key="sunset",
        module=MODULE_WEATHER,
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.weather.sunset if data.weather else None,
        available_fn=lambda data: data.weather is not None,
    ),
    VacationModeSensorDescription(
        key="time_difference",
        translation_key="time_difference",
        module=MODULE_WEATHER,
        native_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=1,
        value_fn=_time_difference,
        attributes_fn=_local_time_attributes,
        available_fn=lambda data: data.weather is not None,
    ),
    # -- air quality ------------------------------------------------------
    VacationModeSensorDescription(
        key="air_quality_index",
        translation_key="air_quality_index",
        module=MODULE_AIR_QUALITY,
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: _air(data, "european_aqi"),
        available_fn=lambda data: data.air_quality is not None,
        attributes_fn=lambda data: {"us_aqi": _air(data, "us_aqi")},
    ),
    VacationModeSensorDescription(
        key="pm2_5",
        module=MODULE_AIR_QUALITY,
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: _air(data, "pm2_5"),
        available_fn=lambda data: data.air_quality is not None,
    ),
    VacationModeSensorDescription(
        key="pm10",
        module=MODULE_AIR_QUALITY,
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: _air(data, "pm10"),
        available_fn=lambda data: data.air_quality is not None,
    ),
    VacationModeSensorDescription(
        key="ozone",
        module=MODULE_AIR_QUALITY,
        device_class=SensorDeviceClass.OZONE,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _air(data, "ozone"),
        available_fn=lambda data: data.air_quality is not None,
    ),
    VacationModeSensorDescription(
        key="nitrogen_dioxide",
        module=MODULE_AIR_QUALITY,
        device_class=SensorDeviceClass.NITROGEN_DIOXIDE,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _air(data, "nitrogen_dioxide"),
        available_fn=lambda data: data.air_quality is not None,
    ),
    VacationModeSensorDescription(
        key="pollen",
        translation_key="pollen",
        module=MODULE_AIR_QUALITY,
        native_unit_of_measurement=POLLEN_UNIT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_pollen_max,
        available_fn=lambda data: data.air_quality is not None,
        attributes_fn=lambda data: {
            field: _air(data, field) for field in POLLEN_FIELDS
        },
    ),
    # -- marine -----------------------------------------------------------
    VacationModeSensorDescription(
        key="water_temperature",
        translation_key="water_temperature",
        module=MODULE_MARINE,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: _marine(data, "sea_surface_temperature"),
        available_fn=lambda data: data.marine is not None,
    ),
    VacationModeSensorDescription(
        key="wave_height",
        translation_key="wave_height",
        module=MODULE_MARINE,
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: _marine(data, "wave_height"),
        available_fn=lambda data: data.marine is not None,
        attributes_fn=lambda data: {
            "wave_period": _marine(data, "wave_period"),
            "wave_direction": _marine(data, "wave_direction"),
        },
    ),
    # -- holidays ---------------------------------------------------------
    VacationModeSensorDescription(
        key="next_holiday",
        translation_key="next_holiday",
        module=MODULE_HOLIDAYS,
        value_fn=lambda data: (
            data.holidays.next.local_name
            if data.holidays and data.holidays.next
            else None
        ),
        available_fn=lambda data: data.holidays is not None,
        attributes_fn=_next_holiday_attributes,
    ),
    VacationModeSensorDescription(
        key="next_holiday_date",
        translation_key="next_holiday_date",
        module=MODULE_HOLIDAYS,
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda data: (
            data.holidays.next.day if data.holidays and data.holidays.next else None
        ),
        available_fn=lambda data: data.holidays is not None,
        attributes_fn=_next_holiday_attributes,
    ),
    # -- currency ---------------------------------------------------------
    VacationModeSensorDescription(
        key="exchange_rate",
        translation_key="exchange_rate",
        module=MODULE_CURRENCY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=4,
        value_fn=lambda data: data.currency.rate if data.currency else None,
        available_fn=lambda data: data.currency is not None,
        attributes_fn=lambda data: (
            {
                "base_currency": data.currency.base,
                "local_currency": data.currency.target,
                "inverse_rate": round(1 / data.currency.rate, 4)
                if data.currency.rate
                else None,
                "date": data.currency.day.isoformat() if data.currency.day else None,
            }
            if data.currency
            else None
        ),
    ),
    # -- travel advice ----------------------------------------------------
    VacationModeSensorDescription(
        key="travel_advisory",
        translation_key="travel_advisory",
        module=MODULE_TRAVEL_ADVICE,
        device_class=SensorDeviceClass.ENUM,
        options=list(ADVISORY_LEVELS),
        value_fn=lambda data: data.advisory.level if data.advisory else None,
        available_fn=lambda data: data.advisory is not None,
        attributes_fn=lambda data: (
            {
                "title": data.advisory.title,
                "country": data.advisory.country_name,
                "summary": data.advisory.summary,
                "last_changes": data.advisory.last_changes,
                "last_modified": data.advisory.last_modified.isoformat()
                if data.advisory.last_modified
                else None,
                "url": data.advisory.url,
            }
            if data.advisory
            else None
        ),
    ),
    # -- earthquakes ------------------------------------------------------
    VacationModeSensorDescription(
        key="earthquake_count",
        translation_key="earthquake_count",
        module=MODULE_EARTHQUAKES,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.earthquakes.count if data.earthquakes else None,
        available_fn=lambda data: data.earthquakes is not None,
        attributes_fn=lambda data: (
            {
                "events": [
                    {
                        "magnitude": event.magnitude,
                        "place": event.place,
                        "time": event.time.isoformat() if event.time else None,
                        "distance_km": event.distance_km,
                        "url": event.url,
                    }
                    for event in data.earthquakes.events[:10]
                ]
            }
            if data.earthquakes
            else None
        ),
    ),
    VacationModeSensorDescription(
        key="earthquake_magnitude",
        translation_key="earthquake_magnitude",
        module=MODULE_EARTHQUAKES,
        suggested_display_precision=1,
        value_fn=lambda data: (
            data.earthquakes.strongest.magnitude
            if data.earthquakes and data.earthquakes.strongest
            else None
        ),
        available_fn=lambda data: data.earthquakes is not None,
        attributes_fn=lambda data: (
            {
                "place": data.earthquakes.strongest.place,
                "time": data.earthquakes.strongest.time.isoformat()
                if data.earthquakes.strongest.time
                else None,
                "distance_km": data.earthquakes.strongest.distance_km,
                "url": data.earthquakes.strongest.url,
            }
            if data.earthquakes and data.earthquakes.strongest
            else None
        ),
    ),
    # -- country info -----------------------------------------------------
    VacationModeSensorDescription(
        key="emergency_number",
        translation_key="emergency_number",
        module=MODULE_COUNTRY_INFO,
        value_fn=lambda data: (
            data.country.emergency.get("general") if data.country else None
        ),
        available_fn=lambda data: data.country is not None,
        attributes_fn=lambda data: (
            dict(data.country.emergency) if data.country else None
        ),
    ),
    VacationModeSensorDescription(
        key="plug_type",
        translation_key="plug_type",
        module=MODULE_COUNTRY_INFO,
        value_fn=lambda data: (
            ", ".join(data.country.plugs)
            if data.country and data.country.plugs
            else None
        ),
        available_fn=lambda data: data.country is not None,
        attributes_fn=lambda data: (
            {
                "plugs": data.country.plugs,
                "voltage": data.country.voltage,
                "frequency": data.country.frequency,
            }
            if data.country
            else None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VacationModeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors for the enabled modules."""
    coordinator = entry.runtime_data
    modules = coordinator.modules
    async_add_entities(
        VacationModeSensor(coordinator, description)
        for description in SENSORS
        if description.module is None or modules.get(description.module)
    )


class VacationModeSensor(VacationModeEntity, SensorEntity):
    """A single value derived from the coordinator data."""

    entity_description: VacationModeSensorDescription

    def __init__(
        self,
        coordinator: VacationModeCoordinator,
        description: VacationModeSensorDescription,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        """Return whether the source of this sensor delivered data."""
        return super().available and self.entity_description.available_fn(
            self.coordinator.data
        )

    @property
    def native_value(self) -> StateType | datetime | date:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the additional details of this sensor."""
        if self.entity_description.attributes_fn is None:
            return None
        return self.entity_description.attributes_fn(self.coordinator.data)
