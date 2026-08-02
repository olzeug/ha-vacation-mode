"""Guards keeping strings.json, en.json and de.json in sync."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aioresponses import aioresponses
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.vacation_mode.binary_sensor import BINARY_SENSORS
from custom_components.vacation_mode.const import ADVISORY_LEVELS, MODULES
from custom_components.vacation_mode.sensor import SENSORS

COMPONENT = Path("custom_components/vacation_mode")
STRINGS = json.loads((COMPONENT / "strings.json").read_text(encoding="utf-8"))
ENGLISH = json.loads((COMPONENT / "translations/en.json").read_text(encoding="utf-8"))
GERMAN = json.loads((COMPONENT / "translations/de.json").read_text(encoding="utf-8"))


def _keys(node: Any, prefix: str = "") -> set[str]:
    """Flatten a translation document into dotted key paths."""
    if not isinstance(node, dict):
        return {prefix}
    return {
        key
        for name, value in node.items()
        for key in _keys(value, f"{prefix}.{name}" if prefix else name)
    }


def test_english_matches_strings() -> None:
    """translations/en.json is the shipped copy of strings.json."""
    assert ENGLISH == STRINGS


def test_german_has_the_same_keys() -> None:
    """No key may be missing from or extra in the German translation."""
    assert _keys(GERMAN) == _keys(ENGLISH)


@pytest.mark.parametrize("module", MODULES)
def test_every_module_is_labelled(module: str) -> None:
    """Both flows label every module toggle."""
    assert module in STRINGS["config"]["step"]["modules"]["data"]
    assert module in STRINGS["options"]["step"]["init"]["data"]


@pytest.mark.parametrize(
    "translation_key",
    sorted(
        description.translation_key
        for description in SENSORS
        if description.translation_key
    ),
)
def test_sensor_translation_keys_exist(translation_key: str) -> None:
    """Every sensor translation key has a name."""
    assert "name" in STRINGS["entity"]["sensor"][translation_key]


@pytest.mark.parametrize(
    "translation_key",
    sorted(
        description.translation_key
        for description in BINARY_SENSORS
        if description.translation_key
    ),
)
def test_binary_sensor_translation_keys_exist(translation_key: str) -> None:
    """Every binary sensor translation key has a name."""
    assert "name" in STRINGS["entity"]["binary_sensor"][translation_key]


def test_local_time_name_has_a_location_placeholder() -> None:
    """The clock names itself after the destination in every language."""
    for document in (STRINGS, GERMAN):
        assert "{location}" in document["entity"]["sensor"]["local_time"]["name"]


def test_weather_name_has_a_location_placeholder() -> None:
    """The weather entity names itself after the destination in every language."""
    for document in (STRINGS, GERMAN):
        assert "{location}" in document["entity"]["weather"]["weather"]["name"]


def test_advisory_states_are_translated() -> None:
    """The enum sensor translates all of its options."""
    states = STRINGS["entity"]["sensor"]["travel_advisory"]["state"]
    assert set(states) == set(ADVISORY_LEVELS)


async def _setup_and_collect_names(
    hass: HomeAssistant,
    mock_sources: aioresponses,
    config_entry: MockConfigEntry,
    language: str,
    unique_ids: set[str],
) -> dict[str, str]:
    """Set up the integration in ``language`` and map unique_id to the shown name.

    The device name is stripped from the front of every ``friendly_name`` so
    the result can be compared directly against the translation documents.
    Only entities whose unique_id is in ``unique_ids`` are collected.
    """
    hass.config.language = language
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    prefix = f"{config_entry.title} "
    names: dict[str, str] = {}
    for entity_entry in registry.entities.values():
        if entity_entry.unique_id not in unique_ids:
            continue
        state = hass.states.get(entity_entry.entity_id)
        assert state is not None
        friendly_name = state.attributes["friendly_name"]
        assert friendly_name.startswith(prefix), (
            f"{entity_entry.entity_id} name {friendly_name!r} lost its device prefix"
        )
        names[entity_entry.unique_id] = friendly_name.removeprefix(prefix)
    return names


@pytest.mark.parametrize(
    ("language", "document"),
    [("en", ENGLISH), ("de", GERMAN)],
    ids=["english", "german"],
)
@pytest.mark.usefixtures("set_states")
async def test_entity_names_resolve_per_language(
    hass: HomeAssistant,
    mock_sources: aioresponses,
    config_entry: MockConfigEntry,
    language: str,
    document: dict[str, Any],
) -> None:
    """Every translated entity must show its localized name, not just German.

    Regression guard: it is easy for a translation key to render correctly in
    German (the language most manual testing happens in) while silently
    falling back to the raw key or the wrong string in English, e.g. if a key
    is only added to strings.json/de.json but not kept identical in en.json.
    """
    unique_ids = {
        f"{config_entry.entry_id}_{description.key}"
        for description in (*SENSORS, *BINARY_SENSORS)
        if description.translation_key
    }
    unique_ids.add(f"{config_entry.entry_id}_local_time")
    unique_ids.add(f"{config_entry.entry_id}_weather")

    names = await _setup_and_collect_names(
        hass, mock_sources, config_entry, language, unique_ids
    )

    for description in SENSORS:
        if not description.translation_key:
            continue
        unique_id = f"{config_entry.entry_id}_{description.key}"
        expected = document["entity"]["sensor"][description.translation_key]["name"]
        assert names[unique_id] == expected

    for description in BINARY_SENSORS:
        if not description.translation_key:
            continue
        unique_id = f"{config_entry.entry_id}_{description.key}"
        expected = document["entity"]["binary_sensor"][description.translation_key][
            "name"
        ]
        assert names[unique_id] == expected

    local_time_template = document["entity"]["sensor"]["local_time"]["name"]
    expected_local_time = local_time_template.format(location="Phuket")
    assert names[f"{config_entry.entry_id}_local_time"] == expected_local_time

    weather_template = document["entity"]["weather"]["weather"]["name"]
    expected_weather = weather_template.format(location="Phuket")
    assert names[f"{config_entry.entry_id}_weather"] == expected_weather
