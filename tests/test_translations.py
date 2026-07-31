"""Guards keeping strings.json, en.json and de.json in sync."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

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


def test_advisory_states_are_translated() -> None:
    """The enum sensor translates all of its options."""
    states = STRINGS["entity"]["sensor"]["travel_advisory"]["state"]
    assert set(states) == set(ADVISORY_LEVELS)
