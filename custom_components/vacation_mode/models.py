"""Data containers shared between the coordinator and the platforms."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, tzinfo
from typing import Any


@dataclass(slots=True)
class Place:
    """Result of a reverse geocoding lookup."""

    country: str | None
    country_code: str | None
    city: str | None
    state: str | None
    display_name: str | None


@dataclass(slots=True)
class CountryInfo:
    """Static per-country facts from the bundled data file."""

    country_code: str
    name_en: str
    name_de: str
    iso3: str | None
    currency: str | None
    emergency: dict[str, str]
    plugs: list[str]
    voltage: int | None
    frequency: int | None
    tap_water: str


@dataclass(slots=True)
class WeatherData:
    """Normalised Open-Meteo forecast response."""

    current: dict[str, float | None]
    daily: list[dict[str, Any]]
    hourly: list[dict[str, Any]]
    sunrise: datetime | None
    sunset: datetime | None
    utc_offset_seconds: int
    timezone: str | None


@dataclass(slots=True)
class Holiday:
    """A single public holiday."""

    day: date
    name: str
    local_name: str
    nationwide: bool


@dataclass(slots=True)
class HolidayInfo:
    """Public holidays for the country the person is currently in."""

    country_code: str
    holidays: list[Holiday]
    today: Holiday | None
    next: Holiday | None


@dataclass(slots=True)
class CurrencyInfo:
    """Exchange rate between the home and the local currency."""

    base: str
    target: str
    rate: float
    day: date | None


@dataclass(slots=True)
class TravelAdvisory:
    """Travel advisory published by the German Federal Foreign Office."""

    level: str
    title: str | None
    country_name: str | None
    summary: str | None
    last_changes: str | None
    last_modified: datetime | None
    url: str | None


@dataclass(slots=True)
class Earthquake:
    """A single seismic event."""

    magnitude: float
    place: str | None
    time: datetime | None
    distance_km: float | None
    url: str | None


@dataclass(slots=True)
class EarthquakeInfo:
    """Recent seismic events around the current location."""

    count: int
    strongest: Earthquake | None
    events: list[Earthquake]


@dataclass(slots=True)
class VacationModeData:
    """Everything the coordinator hands to the entities."""

    latitude: float | None = None
    longitude: float | None = None
    distance_home: float | None = None
    place: Place | None = None
    country: CountryInfo | None = None
    weather: WeatherData | None = None
    # Timezone of the destination, resolved once per update so the entities
    # never have to load it from disk inside the event loop.
    destination_tz: tzinfo | None = None
    air_quality: dict[str, float | None] | None = None
    marine: dict[str, float | None] | None = None
    holidays: HolidayInfo | None = None
    currency: CurrencyInfo | None = None
    advisory: TravelAdvisory | None = None
    earthquakes: EarthquakeInfo | None = None
    errors: dict[str, str] = field(default_factory=dict)
