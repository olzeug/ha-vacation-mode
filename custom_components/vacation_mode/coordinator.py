"""Data update coordinator for Vacation Mode."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from homeassistant.util.location import distance as location_distance

from . import api
from .api import VacationModeApiError
from .const import (
    CONF_HOME_CURRENCY,
    CONF_MODULES,
    CONF_PERSON_ENTITY,
    DEFAULT_HOME_CURRENCY,
    DEFAULT_MODULES,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LOCATION_CHANGE_THRESHOLD_M,
    MODULE_AIR_QUALITY,
    MODULE_COUNTRY_INFO,
    MODULE_CURRENCY,
    MODULE_EARTHQUAKES,
    MODULE_HOLIDAYS,
    MODULE_MARINE,
    MODULE_TRAVEL_ADVICE,
    MODULE_WEATHER,
    TTL_CURRENCY,
    TTL_GEOCODE,
    TTL_HOLIDAYS,
    TTL_TRAVEL_ADVICE,
)
from .country_data import async_get_country_info
from .models import Place, VacationModeData

_LOGGER = logging.getLogger(__name__)

type VacationModeConfigEntry = ConfigEntry[VacationModeCoordinator]


@dataclass(slots=True)
class _CacheEntry:
    """A cached source result together with its invalidation key."""

    key: str
    expires: datetime
    value: Any


class VacationModeCoordinator(DataUpdateCoordinator[VacationModeData]):
    """Polls all configured data sources for the tracked person's location."""

    config_entry: VacationModeConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: VacationModeConfigEntry
    ) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=config_entry,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self._session = async_get_clientsession(hass)
        self._cache: dict[str, _CacheEntry] = {}
        self._geocoded_at: tuple[float, float] | None = None
        self._last_location: tuple[float, float] | None = None

    @property
    def person_entity_id(self) -> str:
        """Entity ID of the tracked person."""
        return self.config_entry.data[CONF_PERSON_ENTITY]

    @property
    def modules(self) -> dict[str, bool]:
        """Enabled modules."""
        return {
            **DEFAULT_MODULES,
            **self.config_entry.options.get(CONF_MODULES, {}),
        }

    def _option(self, key: str, default: Any) -> Any:
        """Read an option with a fallback to the initial config data."""
        return self.config_entry.options.get(
            key, self.config_entry.data.get(key, default)
        )

    async def _async_setup(self) -> None:
        """Register the state listeners before the first refresh."""
        self.config_entry.async_on_unload(
            async_track_state_change_event(
                self.hass, [self.person_entity_id], self._handle_person_change
            )
        )

    # -- location helpers ---------------------------------------------------

    def _current_location(self) -> tuple[float, float] | None:
        """Read the coordinates of the tracked person."""
        state = self.hass.states.get(self.person_entity_id)
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return None
        latitude = state.attributes.get(ATTR_LATITUDE)
        longitude = state.attributes.get(ATTR_LONGITUDE)
        if latitude is None or longitude is None:
            return None
        return float(latitude), float(longitude)

    def _home_location(self) -> tuple[float, float] | None:
        """Read the coordinates of zone.home, falling back to the HA config."""
        if (state := self.hass.states.get("zone.home")) is not None:
            latitude = state.attributes.get(ATTR_LATITUDE)
            longitude = state.attributes.get(ATTR_LONGITUDE)
            if latitude is not None and longitude is not None:
                return float(latitude), float(longitude)
        config = self.hass.config
        if config.latitude is None or config.longitude is None:
            return None
        return config.latitude, config.longitude

    def _distance_home(self, latitude: float, longitude: float) -> float | None:
        """Distance between the person and home in kilometres."""
        if (home := self._home_location()) is None:
            return None
        metres = location_distance(latitude, longitude, home[0], home[1])
        return round(metres / 1000, 2) if metres is not None else None

    @callback
    def _handle_person_change(self, event: Event[EventStateChangedData]) -> None:
        """React to movement of the tracked person."""
        if (location := self._current_location()) is None:
            return
        if self._last_location is None:
            self.hass.async_create_task(self.async_request_refresh())
            return

        moved = location_distance(*location, *self._last_location)
        if moved is not None and moved > LOCATION_CHANGE_THRESHOLD_M:
            _LOGGER.debug("Person moved %.0f m, refreshing", moved)
            self.hass.async_create_task(self.async_request_refresh())
            return

        # Small movements only update the cheap, locally computed values.
        if self.data is not None:
            self.data.latitude, self.data.longitude = location
            self.data.distance_home = self._distance_home(*location)
            self.async_update_listeners()

    # -- source helpers -----------------------------------------------------

    async def _async_source[T](
        self,
        name: str,
        factory: Callable[[], Coroutine[Any, Any, T]],
        errors: dict[str, str],
        *,
        cache_key: str | None = None,
        ttl: timedelta | None = None,
        fallback: T | None = None,
    ) -> T | None:
        """Run one source, keeping failures local to that source."""
        now = dt_util.utcnow()
        cached = self._cache.get(name)
        if (
            ttl is not None
            and cached is not None
            and cached.key == cache_key
            and cached.expires > now
        ):
            return cached.value

        try:
            value = await factory()
        except VacationModeApiError as err:
            _LOGGER.debug("Source %s failed: %s", name, err)
            errors[name] = str(err)
            if cached is not None and cached.key == cache_key:
                return cached.value
            return fallback
        except Exception as err:  # noqa: BLE001 - never break other sources
            _LOGGER.exception("Unexpected error in source %s", name)
            errors[name] = str(err)
            return fallback

        if ttl is not None and cache_key is not None:
            self._cache[name] = _CacheEntry(cache_key, now + ttl, value)
        return value

    async def _async_place(
        self, latitude: float, longitude: float, errors: dict[str, str]
    ) -> Place | None:
        """Reverse geocode, but only after a relevant location change."""
        previous = self.data.place if self.data else None
        if previous is not None and self._geocoded_at is not None:
            moved = location_distance(latitude, longitude, *self._geocoded_at)
            cached = self._cache.get("geocode")
            fresh = cached is not None and cached.expires > dt_util.utcnow()
            if moved is not None and moved <= LOCATION_CHANGE_THRESHOLD_M and fresh:
                return previous

        place = await self._async_source(
            "geocode",
            lambda: api.async_reverse_geocode(
                self._session, latitude, longitude, self.hass.config.language
            ),
            errors,
            cache_key=f"{latitude:.3f},{longitude:.3f}",
            ttl=TTL_GEOCODE,
            fallback=previous,
        )
        if place is not None and "geocode" not in errors:
            self._geocoded_at = (latitude, longitude)
        return place

    # -- update -------------------------------------------------------------

    async def async_force_refresh(self) -> None:
        """Refetch every source, ignoring the cached results and their TTLs."""
        _LOGGER.debug("Forced refresh, dropping %d cached results", len(self._cache))
        self._cache.clear()
        self._geocoded_at = None
        await self.async_refresh()

    async def _async_update_data(self) -> VacationModeData:
        """Fetch every enabled source for the current location."""
        location = self._current_location() or self._last_location
        if location is None:
            raise UpdateFailed(f"No coordinates available for {self.person_entity_id}")

        latitude, longitude = location
        errors: dict[str, str] = {}
        data = VacationModeData(
            latitude=latitude,
            longitude=longitude,
            distance_home=self._distance_home(latitude, longitude),
        )

        modules = self.modules
        data.place = await self._async_place(latitude, longitude, errors)
        country_code = data.place.country_code if data.place else None
        if country_code:
            data.country = await async_get_country_info(self.hass, country_code)

        tasks: dict[str, Coroutine[Any, Any, Any]] = {}

        if modules.get(MODULE_WEATHER):
            tasks["weather"] = self._async_source(
                "weather",
                lambda: api.async_get_forecast(self._session, latitude, longitude),
                errors,
                fallback=self.data.weather if self.data else None,
            )
        if modules.get(MODULE_AIR_QUALITY):
            tasks["air_quality"] = self._async_source(
                "air_quality",
                lambda: api.async_get_air_quality(self._session, latitude, longitude),
                errors,
                fallback=self.data.air_quality if self.data else None,
            )
        if modules.get(MODULE_MARINE):
            tasks["marine"] = self._async_source(
                "marine",
                lambda: api.async_get_marine(self._session, latitude, longitude),
                errors,
            )
        if modules.get(MODULE_EARTHQUAKES):
            tasks["earthquakes"] = self._async_source(
                "earthquakes",
                lambda: api.async_get_earthquakes(self._session, latitude, longitude),
                errors,
                fallback=self.data.earthquakes if self.data else None,
            )
        if modules.get(MODULE_HOLIDAYS) and country_code:
            tasks["holidays"] = self._async_source(
                "holidays",
                lambda: api.async_get_holidays(
                    self._session, country_code, dt_util.now().date()
                ),
                errors,
                cache_key=f"{country_code}-{dt_util.now().date()}",
                ttl=TTL_HOLIDAYS,
            )
        if modules.get(MODULE_CURRENCY) and data.country and data.country.currency:
            base = self._option(CONF_HOME_CURRENCY, DEFAULT_HOME_CURRENCY)
            target = data.country.currency
            tasks["currency"] = self._async_source(
                "currency",
                lambda: api.async_get_exchange_rate(self._session, base, target),
                errors,
                cache_key=f"{base}-{target}",
                ttl=TTL_CURRENCY,
            )
        if modules.get(MODULE_TRAVEL_ADVICE) and country_code:
            iso3 = data.country.iso3 if data.country else None
            tasks["advisory"] = self._async_source(
                "advisory",
                lambda: api.async_get_travel_advice(self._session, country_code, iso3),
                errors,
                cache_key=country_code,
                ttl=TTL_TRAVEL_ADVICE,
            )

        if tasks:
            results = await asyncio.gather(*tasks.values())
            for name, result in zip(tasks, results, strict=True):
                setattr(data, name, result)

        if not modules.get(MODULE_COUNTRY_INFO):
            data.country = None
        data.errors = errors
        self._last_location = location

        if errors:
            _LOGGER.debug("Update finished with failed sources: %s", list(errors))
        return data
