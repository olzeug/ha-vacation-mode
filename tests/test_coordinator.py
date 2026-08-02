"""Tests for the Vacation Mode data update coordinator."""

from __future__ import annotations

from aioresponses import aioresponses
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.vacation_mode.const import (
    ADVISORY_SITUATION,
    LOCATION_CHANGE_THRESHOLD_M,
)

from . import payloads
from .conftest import PERSON_ENTITY, URLS, register_sources


@pytest.mark.usefixtures("setup_integration")
async def test_update_success(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Every source contributes its part to the coordinator data."""
    data = config_entry.runtime_data.data

    assert data.errors == {}
    assert data.place is not None
    assert data.place.country == "Thailand"
    assert data.place.country_code == "TH"
    assert data.country is not None
    assert data.country.currency == "THB"
    assert data.country.emergency["general"] == "191"
    assert data.weather is not None
    assert data.weather.current["temperature_2m"] == 29.4
    assert data.weather.utc_offset_seconds == 25200
    assert len(data.weather.daily) == 7
    assert len(data.weather.hourly) == 24
    assert data.air_quality is not None
    assert data.air_quality["european_aqi"] == 34
    assert data.marine is not None
    assert data.marine["sea_surface_temperature"] == 29.8
    assert data.holidays is not None
    assert len(data.holidays.holidays) == 3
    assert data.currency is not None
    assert data.currency.rate == pytest.approx(37.842)
    assert data.advisory is not None
    assert data.advisory.level == ADVISORY_SITUATION
    assert data.advisory.summary is not None
    assert data.advisory.summary.startswith("Aktuelles: Vor Reisen")
    assert data.advisory.last_changes == (
        "Letzte Änderungen: Sicherheit, Redaktionelle Änderungen"
    )
    assert data.advisory.url == (
        "https://www.auswaertiges-amt.de/de/ReiseUndSicherheit/236302"
    )
    assert data.earthquakes is not None
    assert data.earthquakes.count == 2
    assert data.earthquakes.strongest.magnitude == 4.6
    # Phuket is roughly 9000 km away from the configured home zone.
    assert data.distance_home == pytest.approx(9200, abs=500)


async def test_partial_failure_keeps_other_sources(
    hass: HomeAssistant,
    set_states: None,
    config_entry: MockConfigEntry,
) -> None:
    """A failing source is recorded but does not affect the others."""
    with aioresponses() as mocked:
        register_sources(mocked, failing={"air_quality"})
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    data = config_entry.runtime_data.data

    assert "air_quality" in data.errors
    assert data.air_quality is None
    assert data.weather is not None
    assert data.weather.current["temperature_2m"] == 29.4
    assert data.currency is not None
    assert data.earthquakes is not None
    assert (
        hass.states.get("weather.vacation_mode_traveller_weather").attributes[
            "temperature"
        ]
        == 29.4
    )
    assert (
        hass.states.get("sensor.vacation_mode_traveller_pm2_5").state == "unavailable"
    )


async def test_advisory_without_article_keeps_the_level(
    hass: HomeAssistant,
    set_states: None,
    config_entry: MockConfigEntry,
) -> None:
    """A missing article only costs the summary, not the advisory itself."""
    with aioresponses() as mocked:
        register_sources(mocked, failing={"advisory_article"})
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    data = config_entry.runtime_data.data
    assert "advisory" not in data.errors
    assert data.advisory is not None
    assert data.advisory.level == ADVISORY_SITUATION
    assert data.advisory.summary is None
    assert data.advisory.last_changes is None


async def test_inland_location_has_no_marine_data(
    hass: HomeAssistant,
    set_states: None,
    config_entry: MockConfigEntry,
) -> None:
    """Missing marine data is not treated as an error."""
    with aioresponses() as mocked:
        mocked.get(
            URLS["marine"],
            status=400,
            payload=payloads.MARINE_INLAND,
            repeat=True,
        )
        register_sources(mocked)
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    data = config_entry.runtime_data.data
    assert data.marine is None
    assert "marine" not in data.errors
    assert data.weather is not None


async def test_geocoding_failure_leaves_country_modules_empty(
    hass: HomeAssistant,
    set_states: None,
    config_entry: MockConfigEntry,
) -> None:
    """Without a country the location independent sources still work."""
    with aioresponses() as mocked:
        register_sources(mocked, failing={"geocode"})
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    data = config_entry.runtime_data.data
    assert "geocode" in data.errors
    assert data.place is None
    assert data.country is None
    assert data.holidays is None
    assert data.currency is None
    assert data.weather is not None
    assert data.earthquakes is not None


async def test_setup_succeeds_without_coordinates(
    hass: HomeAssistant,
    mock_sources: aioresponses,
    config_entry: MockConfigEntry,
) -> None:
    """A person without coordinates yet must not block setup of the entry."""
    hass.states.async_set(PERSON_ENTITY, "unknown", {})
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    data = config_entry.runtime_data.data
    assert data.latitude is None
    assert data.longitude is None
    assert data.place is None
    assert data.weather is None


@pytest.mark.usefixtures("setup_integration")
async def test_small_movement_does_not_trigger_refresh(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Moving less than the threshold only recomputes the local values."""
    coordinator = config_entry.runtime_data
    before = coordinator.data.distance_home

    hass.states.async_set(
        PERSON_ENTITY,
        "not_home",
        {
            "latitude": payloads.LATITUDE + 0.01,
            "longitude": payloads.LONGITUDE,
        },
    )
    await hass.async_block_till_done()

    assert coordinator.data.latitude == pytest.approx(payloads.LATITUDE + 0.01)
    assert coordinator.data.distance_home != before
    assert coordinator.data.place is not None


@pytest.mark.usefixtures("setup_integration")
async def test_large_movement_triggers_refresh(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Moving further than the threshold requests a full refresh."""
    coordinator = config_entry.runtime_data
    degrees = (LOCATION_CHANGE_THRESHOLD_M / 111_000) * 3

    hass.states.async_set(
        PERSON_ENTITY,
        "not_home",
        {
            "latitude": payloads.LATITUDE + degrees,
            "longitude": payloads.LONGITUDE,
        },
    )
    await hass.async_block_till_done()
    await coordinator.async_refresh()

    assert coordinator.last_update_success
    assert coordinator.data.latitude == pytest.approx(payloads.LATITUDE + degrees)
