"""Fixtures for the Vacation Mode tests."""

from __future__ import annotations

from collections.abc import Generator
import re
from unittest.mock import patch

from aioresponses import aioresponses
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.vacation_mode.const import (
    CONF_HOME_CURRENCY,
    CONF_MODULES,
    CONF_PERSON_ENTITY,
    DEFAULT_MODULES,
    DOMAIN,
)

from . import payloads

PERSON_ENTITY = "person.traveller"

URLS = {
    "forecast": re.compile(r"^https://api\.open-meteo\.com/v1/forecast.*"),
    "air_quality": re.compile(
        r"^https://air-quality-api\.open-meteo\.com/v1/air-quality.*"
    ),
    "marine": re.compile(r"^https://marine-api\.open-meteo\.com/v1/marine.*"),
    "geocode": re.compile(r"^https://nominatim\.openstreetmap\.org/reverse.*"),
    "holidays_current": re.compile(
        r"^https://date\.nager\.at/api/v3/PublicHolidays/2026/TH.*"
    ),
    "holidays_next": re.compile(
        r"^https://date\.nager\.at/api/v3/PublicHolidays/2027/TH.*"
    ),
    "currency": re.compile(r"^https://api\.frankfurter\.app/latest.*"),
    "advisory_article": re.compile(
        r"^https://www\.auswaertiges-amt\.de/opendata/travelwarning/\d+.*"
    ),
    "advisory": re.compile(
        r"^https://www\.auswaertiges-amt\.de/opendata/travelwarning.*"
    ),
    "earthquakes": re.compile(r"^https://earthquake\.usgs\.gov/fdsnws/event/1/query.*"),
}

RESPONSES = {
    "forecast": payloads.FORECAST,
    "air_quality": payloads.AIR_QUALITY,
    "marine": payloads.MARINE,
    "geocode": payloads.NOMINATIM,
    "holidays_current": payloads.HOLIDAYS_CURRENT_YEAR,
    "holidays_next": payloads.HOLIDAYS_NEXT_YEAR,
    "currency": payloads.EXCHANGE_RATE,
    "advisory_article": payloads.TRAVEL_ADVICE_ARTICLE,
    "advisory": payloads.TRAVEL_ADVICE,
    "earthquakes": payloads.EARTHQUAKES,
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations: None,
) -> None:
    """Make Home Assistant load custom_components in every test."""
    return


@pytest.fixture(autouse=True)
def skip_nominatim_throttle() -> Generator[None]:
    """Skip the one request per second pause of the Nominatim client."""
    with patch("custom_components.vacation_mode.api.NOMINATIM_MIN_INTERVAL", 0):
        yield


def register_sources(
    mocked: aioresponses, failing: set[str] | None = None
) -> aioresponses:
    """Register a canned response for every data source.

    Sources named in ``failing`` answer with HTTP 500 instead. Because
    aioresponses matches in registration order, tests can register their own
    matcher first and still call this helper for the remaining sources.
    """
    failing = failing or set()
    for name, pattern in URLS.items():
        if name in failing:
            mocked.get(pattern, status=500, repeat=True)
        else:
            mocked.get(pattern, payload=RESPONSES[name], repeat=True)
    return mocked


@pytest.fixture
def mock_sources() -> Generator[aioresponses]:
    """Mock every HTTP data source with a successful response."""
    with aioresponses() as mocked:
        yield register_sources(mocked)


@pytest.fixture
def set_states(hass: HomeAssistant) -> None:
    """Put the tracked person and zone.home on the bus."""
    hass.states.async_set(
        PERSON_ENTITY,
        "not_home",
        {
            "friendly_name": "Traveller",
            "latitude": payloads.LATITUDE,
            "longitude": payloads.LONGITUDE,
        },
    )
    hass.states.async_set(
        "zone.home",
        "zoning",
        {
            "latitude": payloads.HOME_LATITUDE,
            "longitude": payloads.HOME_LONGITUDE,
            "radius": 100,
        },
    )


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Return a fully configured entry with every module enabled."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Vacation Mode (Traveller)",
        unique_id=PERSON_ENTITY,
        data={CONF_PERSON_ENTITY: PERSON_ENTITY},
        options={
            CONF_HOME_CURRENCY: "EUR",
            CONF_MODULES: dict(DEFAULT_MODULES),
        },
    )


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant,
    set_states: None,
    mock_sources: aioresponses,
    config_entry: MockConfigEntry,
) -> MockConfigEntry:
    """Set up the integration with all sources mocked."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry
