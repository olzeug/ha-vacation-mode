"""Config and options flow for Vacation Mode."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import selector
import voluptuous as vol

from .const import (
    CONF_HOME_CURRENCY,
    CONF_MODULES,
    CONF_PERSON_ENTITY,
    DEFAULT_HOME_CURRENCY,
    DEFAULT_MODULES,
    DOMAIN,
    MODULES,
)

CURRENCY_SELECTOR = selector.TextSelector(
    selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
)


def _modules_schema(current: dict[str, bool]) -> vol.Schema:
    """Build the schema with one toggle per module."""
    return vol.Schema(
        {
            vol.Required(module, default=current.get(module, True)): (
                selector.BooleanSelector()
            )
            for module in MODULES
        }
    )


class VacationModeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialise the flow."""
        self._data: dict[str, Any] = {}
        self._options: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick the person to track and the home currency."""
        if user_input is not None:
            entity_id = user_input[CONF_PERSON_ENTITY]
            await self.async_set_unique_id(entity_id)
            self._abort_if_unique_id_configured()
            self._data = {CONF_PERSON_ENTITY: entity_id}
            self._options = {CONF_HOME_CURRENCY: user_input[CONF_HOME_CURRENCY].upper()}
            return await self.async_step_modules()

        schema = vol.Schema(
            {
                vol.Required(CONF_PERSON_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=["person", "device_tracker"])
                ),
                vol.Required(
                    CONF_HOME_CURRENCY, default=DEFAULT_HOME_CURRENCY
                ): CURRENCY_SELECTOR,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_modules(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose which modules are active."""
        if user_input is not None:
            self._options[CONF_MODULES] = dict(user_input)
            return self._create_entry()

        return self.async_show_form(
            step_id="modules", data_schema=_modules_schema(DEFAULT_MODULES)
        )

    @callback
    def _create_entry(self) -> ConfigFlowResult:
        """Store the collected input."""
        entity_id = self._data[CONF_PERSON_ENTITY]
        state = self.hass.states.get(entity_id)
        name = state.name if state else entity_id.split(".", 1)[-1]
        return self.async_create_entry(
            title=f"Vacation Mode ({name})",
            data=self._data,
            options=self._options,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> VacationModeOptionsFlow:
        """Return the options flow."""
        return VacationModeOptionsFlow()


class VacationModeOptionsFlow(OptionsFlow):
    """Handle changes after the initial setup."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the home currency and the active modules."""
        current = dict(self.config_entry.options)
        if user_input is not None:
            currency = user_input.pop(CONF_HOME_CURRENCY).upper()
            return self.async_create_entry(
                data={
                    CONF_HOME_CURRENCY: currency,
                    CONF_MODULES: dict(user_input),
                }
            )

        modules = {**DEFAULT_MODULES, **current.get(CONF_MODULES, {})}
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_HOME_CURRENCY,
                    default=current.get(CONF_HOME_CURRENCY, DEFAULT_HOME_CURRENCY),
                ): CURRENCY_SELECTOR,
            }
        ).extend(_modules_schema(modules).schema)
        return self.async_show_form(step_id="init", data_schema=schema)
