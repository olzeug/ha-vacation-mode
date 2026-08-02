"""Tests for the Vacation Mode weather entity."""

from __future__ import annotations

from homeassistant.components.weather import DOMAIN as WEATHER_DOMAIN
from homeassistant.components.weather import SERVICE_GET_FORECASTS
from homeassistant.core import HomeAssistant
import pytest

from custom_components.vacation_mode.weather import to_condition

ENTITY_ID = "weather.vacation_mode_traveller_weather"


@pytest.mark.usefixtures("setup_integration")
async def test_current_conditions(hass: HomeAssistant) -> None:
    """The weather entity mirrors the current Open-Meteo values."""
    state = hass.states.get(ENTITY_ID)

    assert state is not None
    assert state.state == "partlycloudy"
    assert state.attributes["temperature"] == 29.4
    assert state.attributes["apparent_temperature"] == 35.1
    assert state.attributes["humidity"] == 78
    assert state.attributes["pressure"] == 1008.4
    assert state.attributes["wind_speed"] == 14.8
    assert state.attributes["wind_bearing"] == 245
    assert state.attributes["cloud_coverage"] == 55
    assert state.attributes["uv_index"] == 7.35


@pytest.mark.usefixtures("setup_integration")
async def test_daily_forecast(hass: HomeAssistant) -> None:
    """Seven days are exposed with the destination's local day boundaries."""
    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {"entity_id": ENTITY_ID, "type": "daily"},
        blocking=True,
        return_response=True,
    )
    forecast = response[ENTITY_ID]["forecast"]

    assert len(forecast) == 7
    first = forecast[0]
    # 00:00 in Asia/Bangkok is 17:00 UTC on the previous day.
    assert first["datetime"] == "2026-07-31T00:00:00+07:00"
    assert first["condition"] == "rainy"
    assert first["temperature"] == 31.2
    assert first["templow"] == 25.1
    assert first["precipitation"] == 12.4
    assert first["precipitation_probability"] == 80
    assert first["wind_speed"] == 22.3
    assert forecast[6]["condition"] == "lightning-rainy"


@pytest.mark.usefixtures("setup_integration")
async def test_hourly_forecast(hass: HomeAssistant) -> None:
    """Every hour of the first forecast day is exposed."""
    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {"entity_id": ENTITY_ID, "type": "hourly"},
        blocking=True,
        return_response=True,
    )
    forecast = response[ENTITY_ID]["forecast"]

    assert len(forecast) == 24
    assert forecast[0]["datetime"] == "2026-07-31T00:00:00+07:00"
    assert forecast[0]["temperature"] == 27.0
    assert forecast[0]["humidity"] == 80


@pytest.mark.parametrize(
    ("code", "is_day", "expected"),
    [
        (0, True, "sunny"),
        (0, False, "clear-night"),
        (3, True, "cloudy"),
        (48, True, "fog"),
        (65, True, "pouring"),
        (75, True, "snowy"),
        (95, True, "lightning-rainy"),
        (99, True, "hail"),
        (None, True, None),
        (4711, True, None),
    ],
)
def test_condition_mapping(
    code: int | None, is_day: bool, expected: str | None
) -> None:
    """WMO codes map onto Home Assistant conditions."""
    assert to_condition(code, is_day) == expected
