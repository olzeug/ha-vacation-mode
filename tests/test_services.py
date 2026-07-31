"""Tests for the Vacation Mode actions."""

from __future__ import annotations

from aioresponses import aioresponses
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.vacation_mode.const import DOMAIN, SERVICE_REFRESH

from . import payloads
from .conftest import register_sources


def _request_count(mocked: aioresponses, needle: str) -> int:
    """Count the requests aioresponses recorded for a URL fragment."""
    return sum(
        len(calls)
        for (_method, url), calls in mocked.requests.items()
        if needle in str(url)
    )


@pytest.mark.usefixtures("setup_integration")
async def test_service_is_registered(hass: HomeAssistant) -> None:
    """The action exists once the integration is set up."""
    assert hass.services.has_service(DOMAIN, SERVICE_REFRESH)


async def test_refresh_ignores_the_caches(
    hass: HomeAssistant,
    set_states: None,
    config_entry: MockConfigEntry,
) -> None:
    """Cached sources are fetched again instead of being served from cache."""
    with aioresponses() as mocked:
        register_sources(mocked)
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        before = _request_count(mocked, "nominatim")
        assert before == 1

        await hass.services.async_call(DOMAIN, SERVICE_REFRESH, blocking=True)
        await hass.async_block_till_done()

        # Geocoding is cached for a week, so a second request proves the
        # forced refresh bypassed the cache.
        assert _request_count(mocked, "nominatim") == 2

    assert config_entry.runtime_data.data.place is not None


async def test_refresh_recovers_a_failed_source(
    hass: HomeAssistant,
    set_states: None,
    config_entry: MockConfigEntry,
) -> None:
    """A source that failed during setup becomes available again."""
    with aioresponses() as mocked:
        register_sources(mocked, failing={"currency"})
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.runtime_data.data.currency is None

    with aioresponses() as mocked:
        register_sources(mocked)
        await hass.services.async_call(DOMAIN, SERVICE_REFRESH, blocking=True)
        await hass.async_block_till_done()

    data = config_entry.runtime_data.data
    assert data.errors == {}
    assert data.currency is not None
    assert data.currency.rate == pytest.approx(37.842)


@pytest.mark.usefixtures("setup_integration")
async def test_refresh_targets_the_device(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Targeting the integration device refreshes that entry."""
    device = dr.async_get(hass).async_get_device(
        identifiers={(DOMAIN, config_entry.entry_id)}
    )
    assert device is not None

    await hass.services.async_call(
        DOMAIN, SERVICE_REFRESH, {"device_id": device.id}, blocking=True
    )
    await hass.async_block_till_done()

    assert config_entry.runtime_data.last_update_success
    assert config_entry.runtime_data.data.latitude == pytest.approx(payloads.LATITUDE)


@pytest.mark.usefixtures("setup_integration")
async def test_refresh_rejects_a_foreign_target(hass: HomeAssistant) -> None:
    """A target outside the integration is an error, not a silent no-op."""
    other = MockConfigEntry(domain="other")
    other.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=other.entry_id,
        identifiers={("other", "device")},
    )

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, SERVICE_REFRESH, {"device_id": device.id}, blocking=True
        )


async def test_refresh_without_a_loaded_entry(hass: HomeAssistant) -> None:
    """Calling the action without a loaded entry reports it."""
    assert await async_setup_component(hass, DOMAIN, {})

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, SERVICE_REFRESH, blocking=True)
