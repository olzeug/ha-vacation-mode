"""Tests for the Vacation Mode config and options flow."""

from __future__ import annotations

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.vacation_mode.const import (
    CONF_HOME_CURRENCY,
    CONF_MODULES,
    CONF_PERSON_ENTITY,
    DEFAULT_MODULES,
    DOMAIN,
    MODULE_MARINE,
)

from .conftest import PERSON_ENTITY


async def test_full_flow(hass: HomeAssistant, set_states: None) -> None:
    """The two steps produce an entry containing every answer."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PERSON_ENTITY: PERSON_ENTITY, CONF_HOME_CURRENCY: "chf"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "modules"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**DEFAULT_MODULES, MODULE_MARINE: False}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Vacation Mode (Traveller)"
    assert result["data"] == {CONF_PERSON_ENTITY: PERSON_ENTITY}
    assert result["options"][CONF_HOME_CURRENCY] == "CHF"
    assert result["options"][CONF_MODULES][MODULE_MARINE] is False
    assert result["result"].unique_id == PERSON_ENTITY


async def test_flow_aborts_on_duplicate(
    hass: HomeAssistant, set_states: None, config_entry: MockConfigEntry
) -> None:
    """The same person cannot be configured twice."""
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PERSON_ENTITY: PERSON_ENTITY, CONF_HOME_CURRENCY: "EUR"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("setup_integration")
async def test_options_flow_updates_modules(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Options can disable a module and change the home currency."""
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_HOME_CURRENCY: "usd",
            **{**DEFAULT_MODULES, MODULE_MARINE: False},
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    options = config_entry.options
    assert options[CONF_HOME_CURRENCY] == "USD"
    assert options[CONF_MODULES][MODULE_MARINE] is False
