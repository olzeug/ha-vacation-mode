"""Tests for the Vacation Mode sensor platforms."""

from __future__ import annotations

from datetime import date, timedelta
from zoneinfo import ZoneInfo

from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

PREFIX = "vacation_mode_traveller"
DESTINATION_TZ = ZoneInfo("Asia/Bangkok")


@pytest.mark.usefixtures("setup_integration")
async def test_weather_sensors(hass: HomeAssistant) -> None:
    """Values taken from the Open-Meteo forecast."""
    temperature = hass.states.get(f"sensor.{PREFIX}_temperature")
    assert temperature is not None
    assert temperature.state == "29.4"
    assert temperature.attributes["device_class"] == "temperature"
    assert temperature.attributes["unit_of_measurement"] == "°C"

    assert hass.states.get(f"sensor.{PREFIX}_feels_like").state == "35.1"
    assert hass.states.get(f"sensor.{PREFIX}_uv_index").state == "7.35"
    assert hass.states.get(f"sensor.{PREFIX}_maximum_temperature_today").state == "31.2"

    # Open-Meteo returns local timestamps, the sensor exposes them in UTC.
    sunrise = hass.states.get(f"sensor.{PREFIX}_sunrise")
    assert sunrise.state == "2026-07-30T23:14:00+00:00"

    difference = hass.states.get(f"sensor.{PREFIX}_time_difference")
    assert difference.attributes["timezone"] == "Asia/Bangkok"
    assert difference.attributes["utc_offset_seconds"] == 25200


@pytest.mark.usefixtures("setup_integration")
async def test_local_time_sensor(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """The clock of the destination ticks on its own, once a minute."""
    entity_id = f"sensor.{PREFIX}_local_time"

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["timezone"] == "Asia/Bangkok"
    # The name follows the place the traveller is in.
    assert state.attributes["friendly_name"].endswith("Local time Phuket")

    # async_fire_time_changed only forces a pending real-clock timer to run
    # early when the target is genuinely ahead of actual wall-clock time, so
    # the freeze target must be relative to "now" rather than a hardcoded
    # date, which would stop working as soon as that instant is in the past.
    target = dt_util.utcnow() + timedelta(minutes=5)
    freezer.move_to(target)
    async_fire_time_changed(hass, target)
    await hass.async_block_till_done()

    destination = target.astimezone(DESTINATION_TZ)
    state = hass.states.get(entity_id)
    assert state.state == destination.strftime("%H:%M")
    assert state.attributes["date"] == destination.date().isoformat()
    assert state.attributes["utc_offset"] == destination.strftime("%z")
    assert state.attributes["location"] == "Phuket"

    # A minute later without any coordinator refresh.
    target += timedelta(minutes=1)
    freezer.move_to(target)
    async_fire_time_changed(hass, target)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == target.astimezone(
        DESTINATION_TZ
    ).strftime("%H:%M")


async def test_local_time_name_follows_the_traveller(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Moving on renames the clock, the entity ID stays put."""
    entity_id = f"sensor.{PREFIX}_local_time"
    coordinator = setup_integration.runtime_data

    coordinator.data.place.city = "Chiang Mai"
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.attributes["friendly_name"].endswith("Local time Chiang Mai")
    assert state.attributes["location"] == "Chiang Mai"


@pytest.mark.usefixtures("setup_integration")
async def test_context_sensors(hass: HomeAssistant) -> None:
    """Values derived from the country and the remaining sources."""
    country = hass.states.get(f"sensor.{PREFIX}_country")
    assert country.state == "Thailand"
    assert country.attributes["country_code"] == "TH"
    assert country.attributes["city"] == "Phuket"

    distance = hass.states.get(f"sensor.{PREFIX}_distance_from_home")
    assert float(distance.state) == pytest.approx(9200, abs=500)

    rate = hass.states.get(f"sensor.{PREFIX}_exchange_rate")
    assert float(rate.state) == pytest.approx(37.842)
    assert rate.attributes["base_currency"] == "EUR"
    assert rate.attributes["local_currency"] == "THB"

    emergency = hass.states.get(f"sensor.{PREFIX}_emergency_number")
    assert emergency.state == "191"
    assert emergency.attributes["ambulance"] == "1669"

    assert hass.states.get(f"sensor.{PREFIX}_plug_type").state == "A, B, C, O"

    advisory = hass.states.get(f"sensor.{PREFIX}_travel_advisory")
    assert advisory.state == "situation_notice"
    assert advisory.attributes["summary"].startswith("Aktuelles: Vor Reisen")
    assert advisory.attributes["url"].endswith("/ReiseUndSicherheit/236302")

    quakes = hass.states.get(f"sensor.{PREFIX}_earthquakes_7_days")
    assert quakes.state == "2"
    assert hass.states.get(f"sensor.{PREFIX}_strongest_earthquake").state == "4.6"

    # The payload fixture pins the holiday to a fixed calendar date, but
    # "days_until" is computed against the real clock, so it drifts by one
    # every day the suite is run on. Compare against the same formula the
    # sensor itself uses instead of a number that goes stale.
    expected_days_until = (date(2026, 8, 12) - dt_util.now().date()).days

    holiday = hass.states.get(f"sensor.{PREFIX}_next_public_holiday")
    assert holiday.state == "วันแม่แห่งชาติ"
    assert holiday.attributes["date"] == "2026-08-12"
    assert holiday.attributes["days_until"] == expected_days_until

    holiday_date = hass.states.get(f"sensor.{PREFIX}_next_public_holiday_on")
    assert holiday_date.state == "2026-08-12"
    assert holiday_date.attributes["device_class"] == "date"
    assert holiday_date.attributes["days_until"] == expected_days_until


@pytest.mark.usefixtures("setup_integration")
async def test_marine_sensors(hass: HomeAssistant) -> None:
    """Coastal locations expose water temperature and waves."""
    assert hass.states.get(f"sensor.{PREFIX}_water_temperature").state == "29.8"
    waves = hass.states.get(f"sensor.{PREFIX}_wave_height")
    assert waves.state == "1.24"
    assert waves.attributes["wave_period"] == 7.2


@pytest.mark.usefixtures("setup_integration")
async def test_binary_sensors(hass: HomeAssistant) -> None:
    """Country facts and the travel advisory as a yes/no verdict."""
    tap_water = hass.states.get(f"binary_sensor.{PREFIX}_tap_water")
    assert tap_water.state == STATE_ON
    assert tap_water.attributes["rating"] == "unsafe"

    warning = hass.states.get(f"binary_sensor.{PREFIX}_travel_warning")
    assert warning.state == STATE_ON
    assert warning.attributes["level"] == "situation_notice"
    assert warning.attributes["summary"].startswith("Aktuelles: Vor Reisen")
    assert warning.attributes["url"].endswith("/ReiseUndSicherheit/236302")

    assert (
        hass.states.get(f"binary_sensor.{PREFIX}_public_holiday_today").state
        == STATE_OFF
    )
