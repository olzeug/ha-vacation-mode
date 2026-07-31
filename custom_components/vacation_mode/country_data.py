"""Loader for the bundled static country data file."""

from __future__ import annotations

from functools import cache
import logging
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util.yaml import load_yaml_dict

from .models import CountryInfo

_LOGGER = logging.getLogger(__name__)

DATA_FILE = Path(__file__).parent / "data" / "countries.yaml"


@cache
def _load() -> dict[str, Any]:
    """Read and cache the country data file."""
    try:
        return load_yaml_dict(str(DATA_FILE))
    except (OSError, ValueError) as err:
        _LOGGER.error("Unable to read %s: %s", DATA_FILE, err)
        return {}


async def async_get_country_info(
    hass: HomeAssistant, country_code: str
) -> CountryInfo | None:
    """Return the static facts for a country, or None when it is not covered."""
    countries = await hass.async_add_executor_job(_load)
    entry = countries.get(country_code.upper())
    if not isinstance(entry, dict):
        _LOGGER.debug("No country data for %s", country_code)
        return None

    emergency = entry.get("emergency") or {}
    return CountryInfo(
        country_code=country_code.upper(),
        name_en=entry.get("name_en") or country_code.upper(),
        name_de=entry.get("name_de") or country_code.upper(),
        iso3=entry.get("iso3"),
        currency=entry.get("currency"),
        emergency={key: str(value) for key, value in emergency.items()},
        plugs=[str(plug) for plug in entry.get("plugs") or []],
        voltage=entry.get("voltage"),
        frequency=entry.get("frequency"),
        tap_water=entry.get("tap_water") or "unknown",
    )
