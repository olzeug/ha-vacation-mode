"""Recorded API payloads used to mock every data source."""

from __future__ import annotations

from typing import Any

LATITUDE = 7.8804
LONGITUDE = 98.3923
HOME_LATITUDE = 53.1435
HOME_LONGITUDE = 8.2146

_HOURS = [f"2026-07-31T{hour:02d}:00" for hour in range(24)]
_DAYS = [f"2026-07-{day:02d}" for day in range(31, 32)] + [
    f"2026-08-{day:02d}" for day in range(1, 7)
]

FORECAST: dict[str, Any] = {
    "latitude": 7.875,
    "longitude": 98.375,
    "utc_offset_seconds": 25200,
    "timezone": "Asia/Bangkok",
    "timezone_abbreviation": "GMT+7",
    "current": {
        "time": "2026-07-31T09:00",
        "temperature_2m": 29.4,
        "relative_humidity_2m": 78,
        "apparent_temperature": 35.1,
        "is_day": 1,
        "precipitation": 0.0,
        "weather_code": 2,
        "cloud_cover": 55,
        "pressure_msl": 1008.4,
        "wind_speed_10m": 14.8,
        "wind_direction_10m": 245,
        "wind_gusts_10m": 28.1,
        "uv_index": 7.35,
    },
    "hourly": {
        "time": _HOURS,
        "temperature_2m": [27.0 + index % 6 for index in range(24)],
        "relative_humidity_2m": [80] * 24,
        "apparent_temperature": [33.0] * 24,
        "precipitation": [0.0] * 24,
        "precipitation_probability": [20] * 24,
        "weather_code": [2] * 24,
        "cloud_cover": [60] * 24,
        "wind_speed_10m": [12.0] * 24,
        "wind_direction_10m": [240] * 24,
        "wind_gusts_10m": [25.0] * 24,
        "uv_index": [0.0] * 24,
    },
    "daily": {
        "time": _DAYS,
        "weather_code": [80, 2, 3, 61, 2, 1, 95],
        "temperature_2m_max": [31.2, 30.8, 31.5, 29.9, 31.0, 32.1, 30.4],
        "temperature_2m_min": [25.1, 25.3, 25.0, 24.8, 25.2, 25.6, 25.0],
        "apparent_temperature_max": [37.4, 36.9, 37.8, 35.2, 37.1, 38.0, 36.2],
        "sunrise": [f"{day}T06:14" for day in _DAYS],
        "sunset": [f"{day}T18:44" for day in _DAYS],
        "uv_index_max": [9.1, 8.7, 9.4, 6.2, 9.0, 9.6, 7.3],
        "precipitation_sum": [12.4, 1.2, 0.0, 18.9, 0.4, 0.0, 22.1],
        "precipitation_probability_max": [80, 30, 10, 90, 20, 5, 95],
        "wind_speed_10m_max": [22.3, 18.1, 16.4, 25.9, 17.2, 15.8, 28.4],
        "wind_gusts_10m_max": [41.0, 33.5, 30.2, 48.6, 31.7, 29.5, 52.9],
        "wind_direction_10m_dominant": [245, 250, 238, 260, 242, 235, 265],
    },
}

AIR_QUALITY: dict[str, Any] = {
    "latitude": 7.875,
    "longitude": 98.375,
    "utc_offset_seconds": 25200,
    "current": {
        "time": "2026-07-31T09:00",
        "european_aqi": 34,
        "us_aqi": 41,
        "pm10": 18.2,
        "pm2_5": 9.7,
        "carbon_monoxide": 141.0,
        "nitrogen_dioxide": 4.3,
        "sulphur_dioxide": 1.8,
        "ozone": 52.0,
        "alder_pollen": None,
        "birch_pollen": None,
        "grass_pollen": None,
        "mugwort_pollen": None,
        "olive_pollen": None,
        "ragweed_pollen": None,
    },
}

MARINE: dict[str, Any] = {
    "latitude": 7.875,
    "longitude": 98.375,
    "utc_offset_seconds": 25200,
    "current": {
        "time": "2026-07-31T09:00",
        "sea_surface_temperature": 29.8,
        "wave_height": 1.24,
        "wave_period": 7.2,
        "wave_direction": 232,
    },
}

MARINE_INLAND: dict[str, Any] = {
    "error": True,
    "reason": "No data is available for this location",
}

NOMINATIM: dict[str, Any] = {
    "place_id": 123456,
    "lat": "7.8804",
    "lon": "98.3923",
    "display_name": "Phuket, Southern Thailand, Thailand",
    "address": {
        "city": "Phuket",
        "state": "Southern Thailand",
        "country": "Thailand",
        "country_code": "th",
    },
}

HOLIDAYS_CURRENT_YEAR: list[dict[str, Any]] = [
    {
        "date": "2026-07-28",
        "localName": "วันเฉลิมพระชนมพรรษา ร.10",
        "name": "King Vajiralongkorn's Birthday",
        "countryCode": "TH",
        "global": True,
    },
    {
        "date": "2026-08-12",
        "localName": "วันแม่แห่งชาติ",
        "name": "The Queen's Birthday",
        "countryCode": "TH",
        "global": True,
    },
]

HOLIDAYS_NEXT_YEAR: list[dict[str, Any]] = [
    {
        "date": "2027-01-01",
        "localName": "วันขึ้นปีใหม่",
        "name": "New Year's Day",
        "countryCode": "TH",
        "global": True,
    },
]

EXCHANGE_RATE: dict[str, Any] = {
    "amount": 1.0,
    "base": "EUR",
    "date": "2026-07-30",
    "rates": {"THB": 37.842},
}

TRAVEL_ADVICE: dict[str, Any] = {
    "response": {
        "236302": {
            "countryName": "Thailand",
            "iso3CountryCode": "THA",
            "title": "Thailand: Reise- und Sicherheitshinweise",
            "warning": False,
            "partialWarning": False,
            "situationWarning": False,
            "situationPartWarning": True,
            "lastModified": 1753900000000,
            "effective": 1753900000000,
        },
        "236304": {
            "countryName": "Spanien",
            "iso3CountryCode": "ESP",
            "title": "Spanien: Reise- und Sicherheitshinweise",
            "warning": False,
            "partialWarning": False,
            "situationWarning": False,
            "situationPartWarning": False,
            "lastModified": 1753800000000,
        },
        "contentList": {"236302": "Thailand", "236304": "Spanien"},
        "lastModified": 1753900000000,
    }
}

TRAVEL_ADVICE_ARTICLE: dict[str, Any] = {
    "response": {
        "236302": {
            "countryName": "Thailand",
            "iso3CountryCode": "THA",
            "title": "Thailand: Reise- und Sicherheitshinweise",
            "warning": False,
            "partialWarning": False,
            "situationWarning": False,
            "situationPartWarning": True,
            "lastModified": 1753900000000,
            "lastChanges": (
                "Letzte Änderungen:<br><span>Sicherheit</span>"
                "<br><span>Redaktionelle Änderungen</span>"
            ),
            "content": (
                '<div><blockquote class="info-box"><p>'
                "<strong>Lagen können sich schnell verändern.</strong>"
                "</p></blockquote><h2>Aktuelles</h2><p>"
                "<strong>Vor Reisen in das Grenzgebiet zu Kambodscha wird "
                "gewarnt.</strong></p><p>Im Grenzgebiet kam es zu "
                "milit&auml;rischen Auseinandersetzungen.</p></div>"
            ),
        },
        "contentList": {"236302": "Thailand"},
    }
}

EARTHQUAKES: dict[str, Any] = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {
                "mag": 4.6,
                "place": "112 km SW of Phuket, Thailand",
                "time": 1753880000000,
                "url": "https://earthquake.usgs.gov/earthquakes/eventpage/us1000abcd",
            },
            "geometry": {"type": "Point", "coordinates": [97.5, 7.2, 35.0]},
        },
        {
            "type": "Feature",
            "properties": {
                "mag": 3.1,
                "place": "260 km NW of Phuket, Thailand",
                "time": 1753700000000,
                "url": "https://earthquake.usgs.gov/earthquakes/eventpage/us1000efgh",
            },
            "geometry": {"type": "Point", "coordinates": [96.8, 9.4, 12.0]},
        },
    ],
}
