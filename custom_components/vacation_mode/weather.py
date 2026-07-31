"""Weather platform backed by the Open-Meteo forecast."""

from __future__ import annotations

from typing import Any

from homeassistant.components.weather import (
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_FOG,
    ATTR_CONDITION_HAIL,
    ATTR_CONDITION_LIGHTNING_RAINY,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_POURING,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SNOWY_RAINY,
    ATTR_CONDITION_SUNNY,
    Forecast,
    WeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.const import (
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import MODULE_WEATHER
from .coordinator import VacationModeConfigEntry, VacationModeCoordinator
from .entity import VacationModeEntity

# WMO 4677 weather codes as used by Open-Meteo.
CONDITION_MAP: dict[int, str] = {
    0: ATTR_CONDITION_SUNNY,
    1: ATTR_CONDITION_SUNNY,
    2: ATTR_CONDITION_PARTLYCLOUDY,
    3: ATTR_CONDITION_CLOUDY,
    45: ATTR_CONDITION_FOG,
    48: ATTR_CONDITION_FOG,
    51: ATTR_CONDITION_RAINY,
    53: ATTR_CONDITION_RAINY,
    55: ATTR_CONDITION_RAINY,
    56: ATTR_CONDITION_SNOWY_RAINY,
    57: ATTR_CONDITION_SNOWY_RAINY,
    61: ATTR_CONDITION_RAINY,
    63: ATTR_CONDITION_RAINY,
    65: ATTR_CONDITION_POURING,
    66: ATTR_CONDITION_SNOWY_RAINY,
    67: ATTR_CONDITION_SNOWY_RAINY,
    71: ATTR_CONDITION_SNOWY,
    73: ATTR_CONDITION_SNOWY,
    75: ATTR_CONDITION_SNOWY,
    77: ATTR_CONDITION_SNOWY,
    80: ATTR_CONDITION_RAINY,
    81: ATTR_CONDITION_RAINY,
    82: ATTR_CONDITION_POURING,
    85: ATTR_CONDITION_SNOWY,
    86: ATTR_CONDITION_SNOWY,
    95: ATTR_CONDITION_LIGHTNING_RAINY,
    96: ATTR_CONDITION_HAIL,
    99: ATTR_CONDITION_HAIL,
}

FORECAST_KEYS = (
    "native_temperature",
    "native_templow",
    "native_apparent_temperature",
    "native_precipitation",
    "precipitation_probability",
    "native_wind_speed",
    "native_wind_gust_speed",
    "wind_bearing",
    "humidity",
    "cloud_coverage",
    "uv_index",
)


def to_condition(weather_code: Any, is_day: bool = True) -> str | None:
    """Translate a WMO weather code into a Home Assistant condition."""
    if weather_code is None:
        return None
    condition = CONDITION_MAP.get(int(weather_code))
    if condition == ATTR_CONDITION_SUNNY and not is_day:
        return ATTR_CONDITION_CLEAR_NIGHT
    return condition


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VacationModeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the weather entity."""
    coordinator = entry.runtime_data
    if coordinator.modules.get(MODULE_WEATHER):
        async_add_entities([VacationModeWeather(coordinator)])


class VacationModeWeather(VacationModeEntity, WeatherEntity):
    """Current conditions and forecast at the tracked person's location."""

    _attr_name = None
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_wind_speed_unit = UnitOfSpeed.KILOMETERS_PER_HOUR
    _attr_native_pressure_unit = UnitOfPressure.HPA
    _attr_native_precipitation_unit = UnitOfPrecipitationDepth.MILLIMETERS
    _attr_supported_features = (
        WeatherEntityFeature.FORECAST_DAILY | WeatherEntityFeature.FORECAST_HOURLY
    )

    def __init__(self, coordinator: VacationModeCoordinator) -> None:
        """Initialise the weather entity."""
        super().__init__(coordinator, "weather")

    @property
    def available(self) -> bool:
        """Return whether forecast data is present."""
        return super().available and self.coordinator.data.weather is not None

    @property
    def _current(self) -> dict[str, Any]:
        """Current conditions block."""
        if (weather := self.coordinator.data.weather) is None:
            return {}
        return weather.current

    @property
    def condition(self) -> str | None:
        """Return the current condition."""
        return to_condition(
            self._current.get("weather_code"), bool(self._current.get("is_day", 1))
        )

    @property
    def native_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._current.get("temperature_2m")

    @property
    def native_apparent_temperature(self) -> float | None:
        """Return the current apparent temperature."""
        return self._current.get("apparent_temperature")

    @property
    def humidity(self) -> float | None:
        """Return the current relative humidity."""
        return self._current.get("relative_humidity_2m")

    @property
    def native_pressure(self) -> float | None:
        """Return the current air pressure."""
        return self._current.get("pressure_msl")

    @property
    def native_wind_speed(self) -> float | None:
        """Return the current wind speed."""
        return self._current.get("wind_speed_10m")

    @property
    def native_wind_gust_speed(self) -> float | None:
        """Return the current wind gust speed."""
        return self._current.get("wind_gusts_10m")

    @property
    def wind_bearing(self) -> float | None:
        """Return the current wind bearing."""
        return self._current.get("wind_direction_10m")

    @property
    def cloud_coverage(self) -> float | None:
        """Return the current cloud coverage."""
        return self._current.get("cloud_cover")

    @property
    def uv_index(self) -> float | None:
        """Return the current UV index."""
        return self._current.get("uv_index")

    def _forecast(self, entries: list[dict[str, Any]], daytime: bool) -> list[Forecast]:
        """Convert coordinator entries into Home Assistant forecasts."""
        forecasts: list[Forecast] = []
        for entry in entries:
            if (stamp := entry.get("datetime")) is None:
                continue
            forecast = Forecast(
                datetime=stamp.isoformat(),
                condition=to_condition(entry.get("weather_code"), daytime),
            )
            for key in FORECAST_KEYS:
                if (value := entry.get(key)) is not None:
                    forecast[key] = value  # type: ignore[literal-required]
            forecasts.append(forecast)
        return forecasts

    async def async_forecast_daily(self) -> list[Forecast] | None:
        """Return the daily forecast."""
        if (weather := self.coordinator.data.weather) is None:
            return None
        return self._forecast(weather.daily, True)

    async def async_forecast_hourly(self) -> list[Forecast] | None:
        """Return the hourly forecast."""
        if (weather := self.coordinator.data.weather) is None:
            return None
        return self._forecast(weather.hourly, True)
