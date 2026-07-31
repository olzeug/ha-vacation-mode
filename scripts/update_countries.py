#!/usr/bin/env python3
"""Regenerate custom_components/vacation_mode/data/countries.yaml from open data.

Run with:  python scripts/update_countries.py

Downloads four public datasets, merges them and rewrites the bundled YAML file
for every country and territory that has an ISO 4217 currency.  Needs `requests`,
which Home Assistant already pulls in.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys
from typing import Any
import unicodedata

import requests

OUT_FILE = Path(__file__).resolve().parents[1] / (
    "custom_components/vacation_mode/data/countries.yaml"
)

# Base list: names, ISO codes, currencies and German names (upstream of restcountries).
URL_COUNTRIES = (
    "https://raw.githubusercontent.com/mledoze/countries/master/countries.json"
)
# Emergency telephone numbers per country, and a fallback for the ~50 countries
# the API leaves blank.
URL_EMERGENCY = "https://emergencynumberapi.com/api/data/all"
URL_EMERGENCY_WIKI = (
    "https://en.wikipedia.org/w/api.php?action=parse"
    "&page=List_of_emergency_telephone_numbers&prop=wikitext&format=json&formatversion=2"
)
# Plug types, mains voltage and frequency.
URL_MAINS = (
    "https://en.wikipedia.org/w/api.php?action=parse"
    "&page=Mains_electricity_by_country&prop=wikitext&format=json&formatversion=2"
)
# People using safely managed drinking water services (% of population).
URL_WATER = (
    "https://api.worldbank.org/v2/country/all/indicator/SH.H2O.SMDW.ZS"
    "?format=json&per_page=20000&mrnev=1"
)

# Wikipedia spellings that do not appear in any name field of the base list.
NAME_ALIASES = {
    "turkey": "TR",
    "congorepublicofthe": "CG",
    "republicofcongo": "CG",
    "congodemocraticrepublicofthe": "CD",
    "usvirginislands": "VI",
    "thebahamas": "BS",
    "turksandcaicos": "TC",
    "ascensionisland": "SH",
    "tristandacunha": "SH",
}

# Territories the sources omit; they share their parent country's grid and,
# where no numbers of their own are listed, its emergency numbers.
PARENT = {
    "AX": "FI",  # Åland Islands
    "BL": "FR",  # Saint Barthélemy
    "CC": "AU",  # Cocos (Keeling) Islands
    "CX": "AU",  # Christmas Island
    "EH": "MA",  # Western Sahara
    "MP": "US",  # Northern Mariana Islands
    "NF": "AU",  # Norfolk Island
    "PN": "NZ",  # Pitcairn Islands
    "SJ": "NO",  # Svalbard and Jan Mayen
    "TC": "GB",  # Turks and Caicos Islands
    "TK": "NZ",  # Tokelau
    "VA": "IT",  # Vatican City
    "WF": "FR",  # Wallis and Futuna
    "YT": "FR",  # Mayotte
}

# Countries whose first listed currency is withdrawn or not the one travellers use.
CURRENCY = {
    "CK": "NZD",  # the Cook Islands dollar is not traded
    "CU": "CUP",  # CUC was withdrawn in 2021
    "EH": "MAD",
    "PS": "ILS",
    "ZW": "USD",
}

# Hand reviewed emergency numbers as general, police, ambulance, fire.  Both
# online sources have gaps and errors, so reviewed entries are never overwritten;
# everything not listed here comes from the sources.
# fmt: off
EMERGENCY = {
    "AE": ("999", "999", "998", "997"), "AL": ("112", "129", "127", "128"),
    "AR": ("911", "911", "107", "100"), "AT": ("112", "133", "144", "122"),
    "AU": ("000", "000", "000", "000"), "BA": ("112", "122", "124", "123"),
    "BE": ("112", "101", "112", "112"), "BG": ("112", "112", "112", "112"),
    "BR": ("190", "190", "192", "193"), "CA": ("911", "911", "911", "911"),
    "CH": ("112", "117", "144", "118"), "CL": ("133", "133", "131", "132"),
    "CN": ("110", "110", "120", "119"), "CO": ("123", "123", "125", "119"),
    "CR": ("911", "911", "911", "911"), "CU": ("106", "106", "104", "105"),
    "CY": ("112", "199", "199", "199"), "CZ": ("112", "158", "155", "150"),
    "DE": ("112", "110", "112", "112"), "DK": ("112", "114", "112", "112"),
    "DO": ("911", "911", "911", "911"), "EE": ("112", "112", "112", "112"),
    "EG": ("122", "122", "123", "180"), "ES": ("112", "091", "061", "080"),
    "FI": ("112", "112", "112", "112"), "FJ": ("911", "917", "911", "910"),
    "FR": ("112", "17", "15", "18"), "GB": ("999", "999", "999", "999"),
    "GE": ("112", "112", "112", "112"), "GR": ("112", "100", "166", "199"),
    "HK": ("999", "999", "999", "999"), "HR": ("112", "192", "194", "193"),
    "HU": ("112", "107", "104", "105"), "ID": ("112", "110", "118", "113"),
    "IE": ("112", "999", "999", "999"), "IL": ("100", "100", "101", "102"),
    "IN": ("112", "100", "102", "101"), "IS": ("112", "112", "112", "112"),
    "IT": ("112", "113", "118", "115"), "JM": ("119", "119", "110", "110"),
    "JP": ("110", "110", "119", "119"), "KE": ("999", "999", "999", "999"),
    "KR": ("112", "112", "119", "119"), "LK": ("119", "119", "1990", "110"),
    "LT": ("112", "112", "112", "112"), "LU": ("112", "113", "112", "112"),
    "LV": ("112", "110", "113", "112"), "MA": ("190", "190", "150", "150"),
    "ME": ("112", "122", "124", "123"), "MK": ("112", "192", "194", "193"),
    "MT": ("112", "112", "112", "112"), "MU": ("999", "999", "114", "115"),
    "MV": ("119", "119", "102", "118"), "MX": ("911", "911", "911", "911"),
    "MY": ("999", "999", "999", "994"), "NA": ("10111", "10111", "2032276", "2032270"),
    "NL": ("112", "112", "112", "112"), "NO": ("112", "112", "113", "110"),
    "NP": ("100", "100", "102", "101"), "NZ": ("111", "111", "111", "111"),
    "PE": ("105", "105", "106", "116"), "PH": ("911", "911", "911", "911"),
    "PL": ("112", "997", "999", "998"), "PT": ("112", "112", "112", "112"),
    "QA": ("999", "999", "999", "999"), "RO": ("112", "112", "112", "112"),
    "RS": ("112", "192", "194", "193"), "RU": ("112", "102", "103", "101"),
    "SA": ("911", "999", "997", "998"), "SC": ("999", "999", "151", "999"),
    "SE": ("112", "114 14", "112", "112"), "SG": ("999", "999", "995", "995"),
    "SI": ("112", "113", "112", "112"), "SK": ("112", "158", "155", "150"),
    "TH": ("191", "191", "1669", "199"), "TN": ("197", "197", "190", "198"),
    "TR": ("112", "155", "112", "110"), "TW": ("110", "110", "119", "119"),
    "TZ": ("112", "112", "114", "114"), "UA": ("112", "102", "103", "101"),
    "US": ("911", "911", "911", "911"), "VN": ("113", "113", "115", "114"),
    "ZA": ("112", "10111", "10177", "10177"),
}
# fmt: on

# Hand reviewed tap water ratings; they win over the World Bank heuristic below
# because "safely managed" is a supply statistic, not travel advice.
# fmt: off
TAP_WATER = {
    "AE": "caution", "AL": "unsafe", "AR": "caution", "AT": "safe", "AU": "safe",
    "BA": "caution", "BE": "safe", "BG": "caution", "BR": "unsafe", "CA": "safe",
    "CH": "safe", "CL": "safe", "CN": "unsafe", "CO": "caution", "CR": "caution",
    "CU": "unsafe", "CY": "caution", "CZ": "safe", "DE": "safe", "DK": "safe",
    "DO": "unsafe", "EE": "safe", "EG": "unsafe", "ES": "safe", "FI": "safe",
    "FJ": "caution", "FR": "safe", "GB": "safe", "GE": "caution", "GR": "caution",
    "HK": "safe", "HR": "safe", "HU": "safe", "ID": "unsafe", "IE": "safe",
    "IL": "safe", "IN": "unsafe", "IS": "safe", "IT": "safe", "JM": "caution",
    "JP": "safe", "KE": "unsafe", "KR": "safe", "LK": "unsafe", "LT": "safe",
    "LU": "safe", "LV": "safe", "MA": "unsafe", "ME": "caution", "MK": "caution",
    "MT": "safe", "MU": "caution", "MV": "unsafe", "MX": "unsafe", "MY": "caution",
    "NA": "caution", "NL": "safe", "NO": "safe", "NP": "unsafe", "NZ": "safe",
    "PE": "unsafe", "PH": "unsafe", "PL": "safe", "PT": "safe", "QA": "safe",
    "RO": "caution", "RS": "caution", "RU": "unsafe", "SA": "caution", "SC": "caution",
    "SE": "safe", "SG": "safe", "SI": "safe", "SK": "safe", "TH": "unsafe",
    "TN": "unsafe", "TR": "unsafe", "TW": "caution", "TZ": "unsafe", "UA": "unsafe",
    "US": "safe", "VN": "unsafe", "ZA": "caution",
}
# fmt: on

HEADER = """\
# Static country facts used by the Vacation Mode integration.
#
# Generated by scripts/update_countries.py - do not edit by hand, edit the script
# (it carries the reviewed emergency and tap_water values) and run it again.
#
# Sources
#   names, iso3, currency : https://github.com/mledoze/countries (ISO 3166-1 / ISO 4217)
#   emergency             : reviewed values in the script, otherwise
#                           https://emergencynumberapi.com/ and Wikipedia,
#                           "List of emergency telephone numbers"
#   plugs, voltage,
#   frequency             : Wikipedia, "Mains electricity by country"
#                           https://en.wikipedia.org/wiki/Mains_electricity_by_country
#   tap_water             : hand reviewed ratings in the script, otherwise derived
#                           from the World Bank indicator SH.H2O.SMDW.ZS
#                           (safely managed drinking water, % of population):
#                           >= 95 safe, >= 80 caution, below unsafe, no data caution
#
# Schema (all keys required except `iso3`, `voltage`, `frequency`)
#   "<ISO 3166-1 alpha-2>":
#     name_en / name_de : country name
#     iso3              : ISO 3166-1 alpha-3, used to match Foreign Office advisories
#     currency          : ISO 4217 code, used for the exchange rate sensor
#     emergency         : mapping with the keys general, police, ambulance, fire
#     plugs             : list of IEC plug type letters
#     voltage           : mains voltage in volts
#     frequency         : mains frequency in hertz
#     tap_water         : safe | caution | unsafe
#
# Keys are quoted because YAML would otherwise read the country code NO as false.
# `tap_water` is a coarse country level hint, not a guarantee for a specific tap.
"""


def fetch(url: str) -> Any:
    """Download a URL and decode it as JSON."""
    print(f"  {url.split('?')[0]}", file=sys.stderr)
    response = requests.get(
        url, timeout=60, headers={"User-Agent": "ha-vacation-mode/countries-updater"}
    )
    response.raise_for_status()
    return response.json()


def norm(name: str) -> str:
    """Reduce a country name to a comparable key."""
    name = re.sub(r"\bst\.", "saint", name.lower())
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "", name)


def wiki_rows(payload: dict[str, Any], columns: int) -> list[tuple[str, list[str]]]:
    """Yield (country cell, data cells) for every row of a Wikipedia table."""
    wikitext = payload["parse"]["wikitext"]
    wikitext = re.sub(r"<ref[^>]*/>", "", wikitext)
    wikitext = re.sub(r"<ref[^>]*?>.*?</ref>", "", wikitext, flags=re.S)

    rows = []
    for row in re.split(r"\n\|-", wikitext):
        cells = re.split(r"\n\s*\|(?!\|)", row)[1:]
        if len(cells) < 2:
            continue
        match = re.search(r"\{\{[Ff]lag(?:country|icon)?\|([^}|]+)", cells[0])
        if match:
            # A cell may span several columns, so pad instead of requiring a count.
            data = cells[1 : columns + 1]
            rows.append((match.group(1).strip(), data + [""] * (columns - len(data))))
    return rows


def resolve(name: str, by_name: dict[str, str]) -> str | None:
    """Map a Wikipedia country name to an ISO 3166-1 alpha-2 code."""
    key = norm(name)
    return by_name.get(key) or NAME_ALIASES.get(key)


def split_cell(cell: str) -> tuple[int, str]:
    """Split a table cell into its column span and its content."""
    if re.match(r"[^|]*=[^|]*\|", cell):
        attrs, _, cell = cell.rpartition("|")
    else:
        attrs = ""
    span = re.search(r"colspan\s*=\s*\"?(\d)", attrs)
    return int(span.group(1)) if span else 1, cell


def parse_mains(
    payload: dict[str, Any], by_name: dict[str, str]
) -> dict[str, dict[str, Any]]:
    """Extract plug types, voltage and frequency from the Wikipedia table."""
    grids: dict[str, dict[str, Any]] = {}
    for name, cells in wiki_rows(payload, 5):
        code = resolve(re.sub(r"\{\{anchor\|[^}]*\}\}", "", name).strip(), by_name)
        if not code:
            print(f"  ! unmatched mains row: {name}", file=sys.stderr)
            continue
        # Voltage cells look like "230/400 V"; the first number is single phase.
        volts = re.findall(r"(\d{2,3})", cells[2].replace("&nbsp;", " "))
        hertz = re.findall(r"(\d{2})\s*Hz", cells[3].replace("&nbsp;", " "))
        letters = re.findall(r"\b([A-O])\b", re.sub(r"<[^>]+>", " ", cells[0]))
        grids[code] = {
            "plugs": sorted(set(letters)),
            "voltage": int(volts[0]) if volts else None,
            "frequency": int(hertz[0]) if hertz else None,
        }
    return grids


def parse_emergency_wiki(
    payload: dict[str, Any], by_name: dict[str, str]
) -> dict[str, dict[str, str]]:
    """Extract police/ambulance/fire numbers from the Wikipedia table."""
    numbers: dict[str, dict[str, str]] = {}
    for name, cells in wiki_rows(payload, 3):
        code = resolve(name, by_name)
        if not code:
            continue
        values: list[str] = []
        for cell in cells:
            span, body = split_cell(cell)
            bold = re.search(r"'''(.+?)'''", body)
            # A cell may list alternatives ("997, 112"); keep only the first one.
            first = re.split(r"[,;/]|\bor\b", bold.group(1))[0] if bold else ""
            digits = re.sub(r"[^\d\s]", "", first)
            values += [re.sub(r"\s+", "", digits)] * span
        values = (values + ["", "", ""])[:3]
        if any(values):
            numbers[code] = dict(
                zip(("police", "ambulance", "fire"), values, strict=True)
            )
    return numbers


def parse_emergency(
    wiki: dict[str, dict[str, str]], payload: list[dict[str, Any]]
) -> dict[str, dict[str, str]]:
    """Merge the API numbers with the Wikipedia table, which fills the gaps.

    The API knows the per service numbers and the single dispatch number (911,
    999, 000), but leaves about 50 countries blank; Wikipedia covers those, and
    mostly lists a shared 112 where the API is more specific.
    """

    def number(field: dict[str, list[str | None]]) -> str:
        for key in ("All", "Fixed", "GSM"):
            for value in field.get(key) or []:
                if value and value.strip().isdigit():
                    return value.strip()
        return ""

    def combine(known: list[str], dispatch: str, member_112: bool) -> dict[str, str]:
        # A single shared number is the general one, otherwise trust 112 where valid.
        shared = known[0] if len(set(known)) == 1 else ""
        general = (
            dispatch
            or shared
            or ("112" if member_112 else "")
            or next(filter(None, known), "")
        )
        police, ambulance, fire = known
        return {
            "general": general,
            "police": police or general,
            "ambulance": ambulance or general,
            "fire": fire or general,
        }

    numbers: dict[str, dict[str, str]] = {}
    for entry in payload:
        code = entry["Country"]["ISOCode"]
        listed = wiki.get(code, {})
        known = [
            number(entry[field]) or listed.get(service, "")
            for service, field in (
                ("police", "Police"),
                ("ambulance", "Ambulance"),
                ("fire", "Fire"),
            )
        ]
        # Only trust the dispatch number when it looks like an emergency number.
        dispatch = number(entry["Dispatch"])
        services = combine(
            known, dispatch if len(dispatch) <= 3 else "", entry["Member_112"]
        )
        if services["general"]:
            numbers[code] = services

    # Countries the API does not list at all.
    for code, listed in wiki.items():
        if code not in numbers:
            known = [
                listed.get(service, "") for service in ("police", "ambulance", "fire")
            ]
            services = combine(known, "", member_112=False)
            if services["general"]:
                numbers[code] = services
    return numbers


def parse_water(payload: list[Any]) -> dict[str, str]:
    """Turn the World Bank drinking water share into a coarse rating."""
    ratings: dict[str, str] = {}
    for row in payload[1]:
        code, value = row["country"]["id"], row["value"]
        if value is None or len(code) != 2:
            continue
        ratings[code] = (
            "safe" if value >= 95 else "caution" if value >= 80 else "unsafe"
        )
    return ratings


def render(code: str, entry: dict[str, Any]) -> str:
    """Serialise one country block."""
    emergency = ", ".join(
        f'{key}: "{value}"' for key, value in entry["emergency"].items()
    )
    lines = [
        f'"{code}":',
        f"  name_en: {json.dumps(entry['name_en'], ensure_ascii=False)}",
        f"  name_de: {json.dumps(entry['name_de'], ensure_ascii=False)}",
        f"  iso3: {entry['iso3']}",
        f"  currency: {entry['currency']}",
        f"  emergency: {{{emergency}}}",
        f"  plugs: [{', '.join(entry['plugs'])}]",
    ]
    if entry["voltage"]:
        lines.append(f"  voltage: {entry['voltage']}")
    if entry["frequency"]:
        lines.append(f"  frequency: {entry['frequency']}")
    lines.append(f"  tap_water: {entry['tap_water']}")
    return "\n".join(lines)


def main() -> int:
    """Download every dataset, merge it and write countries.yaml."""
    print("Downloading:", file=sys.stderr)
    countries = fetch(URL_COUNTRIES)
    emergency_api = fetch(URL_EMERGENCY)
    emergency_wiki = fetch(URL_EMERGENCY_WIKI)
    mains = fetch(URL_MAINS)
    water = parse_water(fetch(URL_WATER))

    by_name: dict[str, str] = {}
    for country in countries:
        names = {country["name"]["common"], country["name"]["official"]}
        names |= set(country.get("altSpellings", []))
        for translation in country.get("translations", {}).values():
            names |= {translation.get("common", ""), translation.get("official", "")}
        for name in filter(None, names):
            by_name.setdefault(norm(name), country["cca2"])

    emergency = parse_emergency(
        parse_emergency_wiki(emergency_wiki, by_name), emergency_api
    )
    grids = parse_mains(mains, by_name)

    merged: dict[str, dict[str, Any]] = {}
    skipped: list[str] = []
    for country in countries:
        code = country["cca2"]
        currencies = list(country.get("currencies") or {})
        parent = PARENT.get(code, "")
        reviewed = EMERGENCY.get(code)
        numbers = (
            dict(zip(("general", "police", "ambulance", "fire"), reviewed, strict=True))
            if reviewed
            else emergency.get(code) or emergency.get(parent)
        )
        if not currencies or not numbers:
            skipped.append(code)
            continue
        grid = grids.get(code) or grids.get(parent, {})
        merged[code] = {
            "name_en": country["name"]["common"],
            "name_de": country["translations"].get("deu", {}).get("common")
            or country["name"]["common"],
            "iso3": country["cca3"],
            "currency": CURRENCY.get(code, currencies[0]),
            "emergency": numbers,
            "plugs": grid.get("plugs", []),
            "voltage": grid.get("voltage"),
            "frequency": grid.get("frequency"),
            "tap_water": TAP_WATER.get(code) or water.get(code) or "caution",
        }

    blocks = [render(code, merged[code]) for code in sorted(merged)]
    OUT_FILE.write_text(HEADER + "\n" + "\n\n".join(blocks) + "\n", encoding="utf-8")

    no_grid = [code for code, entry in merged.items() if not entry["plugs"]]
    print(
        f"\nWrote {len(merged)} countries to {OUT_FILE}\n"
        f"  skipped (no currency or numbers): {', '.join(sorted(skipped))}\n"
        f"  no plug data: {', '.join(sorted(no_grid)) or 'none'}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
