<div align="center">

<img src="custom_components/vacation_mode/brand/icon.png" alt="Vacation Mode" width="120">

<h1>Vacation Mode</h1>

<p><em>Travel context for Home Assistant, straight from where your people are.</em></p>

<p>
  <a href="https://github.com/olzeug/ha-vacation-mode/actions/workflows/ci.yml"><img src="https://github.com/olzeug/ha-vacation-mode/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/olzeug/ha-vacation-mode/actions/workflows/validate.yml"><img src="https://github.com/olzeug/ha-vacation-mode/actions/workflows/validate.yml/badge.svg" alt="Validate"></a>
  <a href="https://hacs.xyz/"><img src="https://img.shields.io/badge/HACS-Custom-41BDF5.svg" alt="HACS Custom"></a>
</p>

</div>

A Home Assistant custom integration that turns the current location of a person
into travel context: weather, air quality, sea conditions, public holidays,
exchange rate, travel advisory, earthquakes and country facts.

All data sources are free and need **no API key**. The UI is available in
English and German.

## Entities

The entity name is prefixed with the device name, e.g.
`sensor.vacation_mode_traveller_temperature`.

| Entity | Module | Source |
| --- | --- | --- |
| `weather.*` (current + 7 day daily and hourly forecast) | Weather | Open-Meteo |
| `sensor.*_temperature`, `_feels_like`, `_maximum_temperature_today` | Weather | Open-Meteo |
| `sensor.*_humidity`, `_pressure`¹, `_wind_speed`, `_precipitation` | Weather | Open-Meteo |
| `sensor.*_uv_index`, `_sunrise`, `_sunset`, `_time_difference` | Weather | Open-Meteo |
| `sensor.*_local_time` (`HH:MM` at the destination, updated every minute) | Weather | Open-Meteo |
| `sensor.*_air_quality_index`, `_pm2_5`, `_pm10`, `_ozone`¹, `_nitrogen_dioxide`¹ | Air quality | Open-Meteo Air Quality |
| `sensor.*_pollen` (highest of six pollen types, all in the attributes) | Air quality | Open-Meteo Air Quality |
| `sensor.*_water_temperature`, `_wave_height` | Marine | Open-Meteo Marine |
| `sensor.*_country` (city, region and coordinates in the attributes) | always on | Nominatim |
| `sensor.*_distance_from_home` | always on | `zone.home`, no network access |
| `sensor.*_next_public_holiday`, `_next_public_holiday_on` (date, days until) | Holidays | Nager.Date |
| `binary_sensor.*_public_holiday_today` | Holidays | Nager.Date |
| `sensor.*_exchange_rate` | Currency | Frankfurter |
| `sensor.*_travel_advisory`, `binary_sensor.*_travel_warning` (summary and link in the attributes) | Travel advisory | Auswärtiges Amt |
| `sensor.*_earthquakes_7_days`, `_strongest_earthquake` | Earthquakes | USGS |
| `sensor.*_emergency_number`, `_plug_type`, `binary_sensor.*_tap_water` | Country facts | bundled data file |

¹ Disabled by default, enable it in the entity settings if you need it.

Marine data only exists near a coast. Inland the module simply reports no data
instead of failing.

The local time sensor keeps ticking between the polls and renames itself after
the current destination, e.g. **Local time Phuket**. Its entity ID stays
`sensor.*_local_time` regardless of where the traveller is.

## Installation

### HACS (custom repository)

1. Open **HACS → Integrations**.
2. Use the overflow menu (⋮) in the top right and choose **Custom repositories**.
3. Add `https://github.com/olzeug/ha-vacation-mode` with the category
   **Integration**, then click **Add**.
4. Search for **Vacation Mode**, open it and click **Download**.
5. Restart Home Assistant.
6. Go to **Settings → Devices & Services → Add Integration** and search for
   **Vacation Mode**.

### Manual

1. Download the latest `vacation_mode.zip` from the
   [releases page](https://github.com/olzeug/ha-vacation-mode/releases), or copy
   the folder from a checkout of this repository.
2. Place the contents so that the result looks like this:

   ```text
   <config>/custom_components/vacation_mode/__init__.py
   <config>/custom_components/vacation_mode/manifest.json
   ...
   ```

3. Restart Home Assistant.
4. Go to **Settings → Devices & Services → Add Integration** and search for
   **Vacation Mode**.

## Configuration

The config flow has two steps:

1. **Person** — the `person` or `device_tracker` entity to follow, and your home
   currency (ISO 4217, default `EUR`).
2. **Modules** — one checkbox per module. A disabled module is never queried and
   creates no entities.

Everything except the tracked person can be changed later through
**Configure** on the integration entry.

### Travel advisory

Besides the advisory level, the sensor and the binary sensor carry a `summary`
(the first few hundred characters of the article, boilerplate removed),
`last_changes` (what the Foreign Office edited last) and a `url` pointing to the
country page on auswaertiges-amt.de.

## Actions

### `vacation_mode.refresh`

Fetches every enabled source again, ignoring the cached results and their TTLs
— useful when a value went unavailable and you do not want to wait for the next
poll or cache expiry.

```yaml
action: vacation_mode.refresh
target:
  device_id: 1a2b3c4d5e6f7890abcdef1234567890
```

Without a target every loaded Vacation Mode entry is refreshed. Because the
action also re-runs reverse geocoding, do not call it on a schedule — that is
what the 30 minute poll is for.

## How polling works

- The coordinator polls every 30 minutes.
- It additionally listens to the tracked person. Movement below **10 km** only
  recomputes the distance from home; beyond that a full refresh is requested.
- Reverse geocoding runs once per relevant location change, never per poll, to
  stay within the [Nominatim usage policy](https://operations.osmfoundation.org/policies/nominatim/)
  (max. 1 request per second, identifying `User-Agent`).
- Holidays, exchange rate and travel advisory are cached per country.
- A failing source sets its own values to unavailable and leaves the rest
  untouched. The update only fails outright when the tracked person has no
  coordinates at all.

## Data sources

| Source | Used for | Terms |
| --- | --- | --- |
| [Open-Meteo](https://open-meteo.com/) | Weather, air quality, pollen, marine | CC BY 4.0, free for non-commercial use |
| [Nominatim / OpenStreetMap](https://nominatim.org/) | Country and city of the current position | ODbL, © OpenStreetMap contributors |
| [Nager.Date](https://date.nager.at/) | Public holidays | free, ~110 countries |
| [Frankfurter](https://frankfurter.dev/) | Exchange rates | European Central Bank reference rates |
| [Auswärtiges Amt](https://www.auswaertiges-amt.de/de/ReiseUndSicherheit/reise-und-sicherheitshinweise) | Travel advisories | German Federal Foreign Office open data |
| [USGS](https://earthquake.usgs.gov/fdsnws/event/1/) | Earthquakes within 500 km, last 7 days | public domain |

### Country facts

`custom_components/vacation_mode/data/countries.yaml` holds the emergency
numbers, plug types, mains voltage and a tap water rating for 244 countries and
territories. Sources are documented at the top of that file. Each block looks
like this:

```yaml
"PT":
  name_en: "Portugal"
  name_de: "Portugal"
  iso3: PRT
  currency: EUR
  emergency: {general: "112", police: "112", ambulance: "112", fire: "112"}
  plugs: [C, F]
  voltage: 230
  frequency: 50
  tap_water: safe   # safe | caution | unsafe
```

The file is generated, so corrections belong in the generator rather than in the
YAML:

```bash
python scripts/update_countries.py
```

It downloads the country list, emergency numbers, mains electricity data and the
World Bank drinking water indicator, then rewrites the file. Emergency numbers
and tap water ratings that have been reviewed by hand live in `EMERGENCY` and
`TAP_WATER` inside the script and are never overwritten by the online sources —
fix them there. The `tap_water` rating is a coarse country level hint, not a
guarantee for a specific tap. Pull requests that correct the data are welcome.

## Development

No Home Assistant installation or container is needed —
`pytest-homeassistant-custom-component` brings its own Home Assistant.

```bash
python3.13 -m venv .venv
.venv/bin/pip install -r requirements_test.txt
.venv/bin/pytest -q
```

With coverage, exactly as CI runs it:

```bash
.venv/bin/pytest --cov=custom_components.vacation_mode --cov-report=term-missing -q
```

Linting and formatting:

```bash
.venv/bin/pip install ruff
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

Every HTTP call is mocked with `aioresponses`; the test suite never touches a
real API.

### Brand icon

Starting with Home Assistant 2026.3, custom integrations can include their own brand images (icons and logos) directly in the integration directory.

```text
custom_components/vacation_mode/brand/icon.png      # 256x256
custom_components/vacation_mode/brand/icon@2x.png   # 512x512
```

`custom_components/vacation_mode/brand/icon.png` and `custom_components/vacation_mode/brand/icon@2x.png` are those files — square, trimmed of
empty edges and readable on both the light and the dark theme. No `logo.png` is
supplied: the mark carries no wordmark, and Home Assistant falls back to the
icon wherever a logo would be used.

## License

Released under the [MIT License](LICENSE).
