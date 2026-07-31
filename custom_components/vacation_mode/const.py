"""Constants for the Vacation Mode integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "vacation_mode"
MANUFACTURER: Final = "Vacation Mode"

DEFAULT_SCAN_INTERVAL: Final = timedelta(minutes=30)
REQUEST_TIMEOUT: Final = 20

SERVICE_REFRESH: Final = "refresh"

CONF_PERSON_ENTITY: Final = "person_entity"
CONF_HOME_CURRENCY: Final = "home_currency"
CONF_MODULES: Final = "modules"

DEFAULT_HOME_CURRENCY: Final = "EUR"

MODULE_WEATHER: Final = "weather"
MODULE_AIR_QUALITY: Final = "air_quality"
MODULE_MARINE: Final = "marine"
MODULE_HOLIDAYS: Final = "holidays"
MODULE_CURRENCY: Final = "currency"
MODULE_TRAVEL_ADVICE: Final = "travel_advice"
MODULE_EARTHQUAKES: Final = "earthquakes"
MODULE_COUNTRY_INFO: Final = "country_info"

MODULES: Final = (
    MODULE_WEATHER,
    MODULE_AIR_QUALITY,
    MODULE_MARINE,
    MODULE_HOLIDAYS,
    MODULE_CURRENCY,
    MODULE_TRAVEL_ADVICE,
    MODULE_EARTHQUAKES,
    MODULE_COUNTRY_INFO,
)

# Modules that are of no use without a resolved country code.
COUNTRY_MODULES: Final = (
    MODULE_HOLIDAYS,
    MODULE_CURRENCY,
    MODULE_TRAVEL_ADVICE,
    MODULE_COUNTRY_INFO,
)

DEFAULT_MODULES: Final[dict[str, bool]] = {module: True for module in MODULES}

# Distance the tracked person has to move before location dependent data
# (reverse geocoding, weather, ...) is refetched.
LOCATION_CHANGE_THRESHOLD_M: Final = 10_000

# Earthquake query window.
EARTHQUAKE_RADIUS_KM: Final = 500
EARTHQUAKE_DAYS: Final = 7
EARTHQUAKE_MIN_MAGNITUDE: Final = 2.5

# Cache lifetimes for data that does not change on every poll.
TTL_HOLIDAYS: Final = timedelta(days=1)
TTL_TRAVEL_ADVICE: Final = timedelta(hours=6)
TTL_CURRENCY: Final = timedelta(hours=6)
TTL_GEOCODE: Final = timedelta(days=7)

TAP_WATER_SAFE: Final = "safe"

ADVISORY_NONE: Final = "none"
ADVISORY_SITUATION: Final = "situation_notice"
ADVISORY_PARTIAL: Final = "partial_travel_warning"
ADVISORY_WARNING: Final = "travel_warning"
ADVISORY_LEVELS: Final = (
    ADVISORY_NONE,
    ADVISORY_SITUATION,
    ADVISORY_PARTIAL,
    ADVISORY_WARNING,
)
