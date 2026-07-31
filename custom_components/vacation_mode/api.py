"""Async clients for the free data sources used by Vacation Mode."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta, timezone
import html
import logging
import re
from typing import Any

import aiohttp
from aiohttp import ClientSession
from homeassistant.util import dt as dt_util
from homeassistant.util.location import distance as location_distance

from .const import (
    ADVISORY_NONE,
    ADVISORY_PARTIAL,
    ADVISORY_SITUATION,
    ADVISORY_WARNING,
    EARTHQUAKE_DAYS,
    EARTHQUAKE_MIN_MAGNITUDE,
    EARTHQUAKE_RADIUS_KM,
    REQUEST_TIMEOUT,
)
from .models import (
    CurrencyInfo,
    Earthquake,
    EarthquakeInfo,
    Holiday,
    HolidayInfo,
    Place,
    TravelAdvisory,
    WeatherData,
)

_LOGGER = logging.getLogger(__name__)

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
NAGER_URL = "https://date.nager.at/api/v3/PublicHolidays"
EXCHANGE_RATE_URL = "https://open.er-api.com/v6/latest"
TRAVEL_ADVICE_URL = "https://www.auswaertiges-amt.de/opendata/travelwarning"
TRAVEL_ADVICE_PAGE_URL = "https://www.auswaertiges-amt.de/de/ReiseUndSicherheit"
USGS_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"

USER_AGENT = "ha-vacation-mode/0.3.0 (+https://github.com/olzeug/ha-vacation-mode)"

CURRENT_FIELDS = (
    "temperature_2m",
    "relative_humidity_2m",
    "apparent_temperature",
    "is_day",
    "precipitation",
    "weather_code",
    "cloud_cover",
    "pressure_msl",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
    "uv_index",
)
HOURLY_FIELDS = (
    "temperature_2m",
    "relative_humidity_2m",
    "apparent_temperature",
    "precipitation",
    "precipitation_probability",
    "weather_code",
    "cloud_cover",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
    "uv_index",
)
DAILY_FIELDS = (
    "weather_code",
    "temperature_2m_max",
    "temperature_2m_min",
    "apparent_temperature_max",
    "sunrise",
    "sunset",
    "uv_index_max",
    "precipitation_sum",
    "precipitation_probability_max",
    "wind_speed_10m_max",
    "wind_gusts_10m_max",
    "wind_direction_10m_dominant",
)
AIR_QUALITY_FIELDS = (
    "european_aqi",
    "us_aqi",
    "pm10",
    "pm2_5",
    "carbon_monoxide",
    "nitrogen_dioxide",
    "sulphur_dioxide",
    "ozone",
    "alder_pollen",
    "birch_pollen",
    "grass_pollen",
    "mugwort_pollen",
    "olive_pollen",
    "ragweed_pollen",
)
MARINE_FIELDS = (
    "sea_surface_temperature",
    "wave_height",
    "wave_period",
    "wave_direction",
)

# The advisory article is HTML. Every country page starts with the same
# boilerplate info box, which is dropped before the text is shortened.
ADVISORY_SUMMARY_LENGTH = 400
ADVISORY_CHANGES_LENGTH = 100
_ADVISORY_INFO_BOX = re.compile(
    r"^\s*(?:<div>\s*)?<blockquote\b.*?</blockquote>", re.DOTALL
)
_ADVISORY_HEADING = re.compile(r"</h\d>", re.IGNORECASE)
_ADVISORY_LINE_BREAK = re.compile(r"<br\s*/?>", re.IGNORECASE)
_ADVISORY_TAG = re.compile(r"<[^>]+>")
_ADVISORY_LOOSE_PUNCTUATION = re.compile(r"\s+([,.;:!?])")

# Nominatim's usage policy allows at most one request per second.
NOMINATIM_MIN_INTERVAL = 1.0
_nominatim_lock = asyncio.Lock()
_nominatim_last_call = 0.0


class VacationModeApiError(Exception):
    """Raised when a data source cannot be queried."""


async def _fetch_json(
    session: ClientSession,
    url: str,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> Any:
    """Fetch and decode a JSON document."""
    try:
        async with session.get(
            url,
            params=params,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
        ) as response:
            if response.status != 200:
                raise VacationModeApiError(f"{url} returned HTTP {response.status}")
            return await response.json(content_type=None)
    except TimeoutError as err:
        raise VacationModeApiError(f"{url} timed out") from err
    except aiohttp.ClientError as err:
        raise VacationModeApiError(f"{url} failed: {err}") from err
    except ValueError as err:
        raise VacationModeApiError(f"{url} returned invalid JSON: {err}") from err


def _tzinfo(offset_seconds: int) -> timezone:
    """Build a fixed offset timezone for the target location."""
    return timezone(timedelta(seconds=offset_seconds))


def _parse_local(value: str | None, tzinfo: timezone) -> datetime | None:
    """Parse a naive Open-Meteo timestamp as local time of the target location."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).replace(tzinfo=tzinfo)
    except ValueError:
        return None


def _series(payload: dict[str, Any], section: str, key: str) -> list[Any]:
    """Return one series of a time indexed Open-Meteo section."""
    values = payload.get(section, {}).get(key)
    return values if isinstance(values, list) else []


async def async_get_forecast(
    session: ClientSession, latitude: float, longitude: float
) -> WeatherData:
    """Fetch current conditions and the 7 day forecast from Open-Meteo."""
    payload = await _fetch_json(
        session,
        FORECAST_URL,
        {
            "latitude": latitude,
            "longitude": longitude,
            "current": ",".join(CURRENT_FIELDS),
            "hourly": ",".join(HOURLY_FIELDS),
            "daily": ",".join(DAILY_FIELDS),
            "timezone": "auto",
            "forecast_days": 7,
        },
    )
    if not isinstance(payload, dict) or "current" not in payload:
        raise VacationModeApiError("Open-Meteo returned an unexpected payload")

    offset = int(payload.get("utc_offset_seconds") or 0)
    tzinfo = _tzinfo(offset)
    current = {key: payload["current"].get(key) for key in CURRENT_FIELDS}

    times = _series(payload, "daily", "time")
    daily = [
        {
            "datetime": _parse_local(f"{day}T00:00", tzinfo),
            "weather_code": _at(payload, "daily", "weather_code", index),
            "native_temperature": _at(payload, "daily", "temperature_2m_max", index),
            "native_templow": _at(payload, "daily", "temperature_2m_min", index),
            "native_apparent_temperature": _at(
                payload, "daily", "apparent_temperature_max", index
            ),
            "uv_index": _at(payload, "daily", "uv_index_max", index),
            "native_precipitation": _at(payload, "daily", "precipitation_sum", index),
            "precipitation_probability": _at(
                payload, "daily", "precipitation_probability_max", index
            ),
            "native_wind_speed": _at(payload, "daily", "wind_speed_10m_max", index),
            "native_wind_gust_speed": _at(
                payload, "daily", "wind_gusts_10m_max", index
            ),
            "wind_bearing": _at(payload, "daily", "wind_direction_10m_dominant", index),
            "sunrise": _parse_local(_at(payload, "daily", "sunrise", index), tzinfo),
            "sunset": _parse_local(_at(payload, "daily", "sunset", index), tzinfo),
        }
        for index, day in enumerate(times)
    ]

    hourly_times = _series(payload, "hourly", "time")
    hourly = [
        {
            "datetime": _parse_local(stamp, tzinfo),
            "weather_code": _at(payload, "hourly", "weather_code", index),
            "native_temperature": _at(payload, "hourly", "temperature_2m", index),
            "native_apparent_temperature": _at(
                payload, "hourly", "apparent_temperature", index
            ),
            "humidity": _at(payload, "hourly", "relative_humidity_2m", index),
            "uv_index": _at(payload, "hourly", "uv_index", index),
            "native_precipitation": _at(payload, "hourly", "precipitation", index),
            "precipitation_probability": _at(
                payload, "hourly", "precipitation_probability", index
            ),
            "cloud_coverage": _at(payload, "hourly", "cloud_cover", index),
            "native_wind_speed": _at(payload, "hourly", "wind_speed_10m", index),
            "native_wind_gust_speed": _at(payload, "hourly", "wind_gusts_10m", index),
            "wind_bearing": _at(payload, "hourly", "wind_direction_10m", index),
        }
        for index, stamp in enumerate(hourly_times)
    ]

    first_day = daily[0] if daily else {}
    return WeatherData(
        current=current,
        daily=daily,
        hourly=hourly,
        sunrise=first_day.get("sunrise"),
        sunset=first_day.get("sunset"),
        utc_offset_seconds=offset,
        timezone=payload.get("timezone"),
    )


def _at(payload: dict[str, Any], section: str, key: str, index: int) -> Any:
    """Return one value of a time indexed series, or None when absent."""
    values = _series(payload, section, key)
    if index < len(values):
        return values[index]
    return None


async def async_get_air_quality(
    session: ClientSession, latitude: float, longitude: float
) -> dict[str, float | None]:
    """Fetch air quality and pollen values from Open-Meteo."""
    payload = await _fetch_json(
        session,
        AIR_QUALITY_URL,
        {
            "latitude": latitude,
            "longitude": longitude,
            "current": ",".join(AIR_QUALITY_FIELDS),
            "timezone": "auto",
        },
    )
    current = payload.get("current") if isinstance(payload, dict) else None
    if not isinstance(current, dict):
        raise VacationModeApiError("Air quality API returned an unexpected payload")
    return {key: current.get(key) for key in AIR_QUALITY_FIELDS}


async def async_get_marine(
    session: ClientSession, latitude: float, longitude: float
) -> dict[str, float | None] | None:
    """Fetch marine conditions, or None when the location is not coastal."""
    try:
        payload = await _fetch_json(
            session,
            MARINE_URL,
            {
                "latitude": latitude,
                "longitude": longitude,
                "current": ",".join(MARINE_FIELDS),
                "timezone": "auto",
            },
        )
    except VacationModeApiError as err:
        # Inland coordinates are answered with HTTP 400 rather than empty data.
        _LOGGER.debug("No marine data for %s/%s: %s", latitude, longitude, err)
        return None

    current = payload.get("current") if isinstance(payload, dict) else None
    if not isinstance(current, dict):
        return None
    values = {key: current.get(key) for key in MARINE_FIELDS}
    if all(value is None for value in values.values()):
        return None
    return values


async def async_reverse_geocode(
    session: ClientSession, latitude: float, longitude: float, language: str
) -> Place:
    """Resolve coordinates to a place using Nominatim."""
    global _nominatim_last_call  # noqa: PLW0603

    async with _nominatim_lock:
        elapsed = asyncio.get_running_loop().time() - _nominatim_last_call
        if elapsed < NOMINATIM_MIN_INTERVAL:
            await asyncio.sleep(NOMINATIM_MIN_INTERVAL - elapsed)
        try:
            payload = await _fetch_json(
                session,
                NOMINATIM_URL,
                {
                    "lat": latitude,
                    "lon": longitude,
                    "format": "jsonv2",
                    "zoom": 10,
                    "accept-language": language,
                },
                {"User-Agent": USER_AGENT},
            )
        finally:
            _nominatim_last_call = asyncio.get_running_loop().time()

    if not isinstance(payload, dict) or "address" not in payload:
        raise VacationModeApiError("Nominatim returned an unexpected payload")

    address = payload["address"]
    country_code = address.get("country_code")
    return Place(
        country=address.get("country"),
        country_code=country_code.upper() if country_code else None,
        city=address.get("city")
        or address.get("town")
        or address.get("village")
        or address.get("municipality"),
        state=address.get("state"),
        display_name=payload.get("display_name"),
    )


async def async_get_holidays(
    session: ClientSession, country_code: str, today: date
) -> HolidayInfo:
    """Fetch public holidays for the current and next year from Nager.Date."""
    holidays: list[Holiday] = []
    for year in (today.year, today.year + 1):
        try:
            payload = await _fetch_json(session, f"{NAGER_URL}/{year}/{country_code}")
        except VacationModeApiError as err:
            if year == today.year:
                raise
            # Next year is frequently not published yet.
            _LOGGER.debug("No holidays for %s/%s: %s", country_code, year, err)
            continue
        if not isinstance(payload, list):
            continue
        for item in payload:
            try:
                day = date.fromisoformat(item["date"])
            except (KeyError, TypeError, ValueError):
                continue
            holidays.append(
                Holiday(
                    day=day,
                    name=item.get("name") or "",
                    local_name=item.get("localName") or item.get("name") or "",
                    nationwide=bool(item.get("global", True)),
                )
            )

    holidays.sort(key=lambda holiday: holiday.day)
    return HolidayInfo(
        country_code=country_code,
        holidays=holidays,
        today=next((h for h in holidays if h.day == today), None),
        next=next((h for h in holidays if h.day >= today), None),
    )


async def async_get_exchange_rate(
    session: ClientSession, base: str, target: str
) -> CurrencyInfo:
    """Fetch the exchange rate between two currencies from open.er-api.com."""
    if base == target:
        return CurrencyInfo(base=base, target=target, rate=1.0, day=None)

    payload = await _fetch_json(session, f"{EXCHANGE_RATE_URL}/{base}")
    rates = payload.get("rates") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("result") != "success"
        or not isinstance(rates, dict)
        or target not in rates
    ):
        raise VacationModeApiError(f"No exchange rate for {base}/{target}")

    try:
        day = datetime.fromtimestamp(payload["time_last_update_unix"], tz=UTC).date()
    except (KeyError, TypeError, ValueError, OSError):
        day = None
    return CurrencyInfo(base=base, target=target, rate=float(rates[target]), day=day)


def _plain_text(value: str | None, limit: int) -> str | None:
    """Condense one HTML block of an advisory into a short plain text."""
    if not value:
        return None
    text = _ADVISORY_INFO_BOX.sub("", value, count=1)
    text = _ADVISORY_HEADING.sub(": ", text)
    text = html.unescape(_ADVISORY_TAG.sub(" ", text))
    text = _ADVISORY_LOOSE_PUNCTUATION.sub(r"\1", " ".join(text.split()))
    if len(text) <= limit:
        return text or None
    return f"{text[:limit].rsplit(' ', 1)[0].rstrip(' ,.;:')} …"


def _advisory_changes(value: str | None) -> str | None:
    """Flatten the list of recent edits into a single line."""
    parts = [
        part
        for raw in _ADVISORY_LINE_BREAK.split(value or "")
        if (part := _plain_text(raw, ADVISORY_CHANGES_LENGTH))
    ]
    if not parts:
        return None
    heading, *changes = parts
    return f"{heading} {', '.join(changes)}" if changes else heading


def _advisory_level(entry: dict[str, Any]) -> str:
    """Derive a single advisory level from the Foreign Office flags."""
    if entry.get("warning"):
        return ADVISORY_WARNING
    if entry.get("partialWarning"):
        return ADVISORY_PARTIAL
    if entry.get("situationWarning") or entry.get("situationPartWarning"):
        return ADVISORY_SITUATION
    return ADVISORY_NONE


async def _async_advisory_details(
    session: ClientSession, content_id: str
) -> tuple[str | None, str | None]:
    """Fetch the article of one advisory and return its summary and changes."""
    payload = await _fetch_json(session, f"{TRAVEL_ADVICE_URL}/{content_id}")
    response = payload.get("response") if isinstance(payload, dict) else None
    entry = response.get(content_id) if isinstance(response, dict) else None
    if not isinstance(entry, dict):
        raise VacationModeApiError(f"No advisory article for {content_id}")
    return (
        _plain_text(entry.get("content"), ADVISORY_SUMMARY_LENGTH),
        _advisory_changes(entry.get("lastChanges")),
    )


async def async_get_travel_advice(
    session: ClientSession, country_code: str, iso3: str | None
) -> TravelAdvisory:
    """Fetch the German Federal Foreign Office advisory for a country."""
    payload = await _fetch_json(session, TRAVEL_ADVICE_URL)
    response = payload.get("response") if isinstance(payload, dict) else None
    if not isinstance(response, dict):
        raise VacationModeApiError("Travel advice API returned an unexpected payload")

    wanted = {code for code in (iso3, country_code) if code}
    for content_id, entry in response.items():
        if not isinstance(entry, dict):
            continue
        codes = {
            str(entry.get(key)).upper()
            for key in ("iso3CountryCode", "countryCode")
            if entry.get(key)
        }
        if not codes & wanted:
            continue

        last_modified = None
        if (stamp := entry.get("lastModified")) is not None:
            last_modified = dt_util.utc_from_timestamp(int(stamp) / 1000)

        try:
            summary, last_changes = await _async_advisory_details(session, content_id)
        except VacationModeApiError as err:
            # The overview alone is still worth reporting.
            _LOGGER.debug("No advisory article for %s: %s", country_code, err)
            summary = last_changes = None

        return TravelAdvisory(
            level=_advisory_level(entry),
            title=entry.get("title"),
            country_name=entry.get("countryName"),
            summary=summary,
            last_changes=last_changes,
            last_modified=last_modified,
            url=f"{TRAVEL_ADVICE_PAGE_URL}/{content_id}",
        )

    raise VacationModeApiError(f"No travel advice entry for {country_code}")


async def async_get_earthquakes(
    session: ClientSession, latitude: float, longitude: float
) -> EarthquakeInfo:
    """Fetch recent seismic events around the location from the USGS."""
    start = dt_util.utcnow() - timedelta(days=EARTHQUAKE_DAYS)
    payload = await _fetch_json(
        session,
        USGS_URL,
        {
            "format": "geojson",
            "latitude": latitude,
            "longitude": longitude,
            "maxradiuskm": EARTHQUAKE_RADIUS_KM,
            "starttime": start.strftime("%Y-%m-%dT%H:%M:%S"),
            "minmagnitude": EARTHQUAKE_MIN_MAGNITUDE,
            "orderby": "magnitude",
        },
    )
    features = payload.get("features") if isinstance(payload, dict) else None
    if not isinstance(features, list):
        raise VacationModeApiError("USGS returned an unexpected payload")

    events: list[Earthquake] = []
    for feature in features:
        properties = feature.get("properties") or {}
        coordinates = (feature.get("geometry") or {}).get("coordinates") or []
        magnitude = properties.get("mag")
        if magnitude is None:
            continue
        event_time = None
        if (stamp := properties.get("time")) is not None:
            event_time = dt_util.utc_from_timestamp(stamp / 1000)
        distance_km = None
        if len(coordinates) >= 2:
            metres = location_distance(
                latitude, longitude, coordinates[1], coordinates[0]
            )
            distance_km = round(metres / 1000, 1) if metres is not None else None
        events.append(
            Earthquake(
                magnitude=float(magnitude),
                place=properties.get("place"),
                time=event_time,
                distance_km=distance_km,
                url=properties.get("url"),
            )
        )

    events.sort(key=lambda event: event.magnitude, reverse=True)
    return EarthquakeInfo(
        count=len(events),
        strongest=events[0] if events else None,
        events=events,
    )
