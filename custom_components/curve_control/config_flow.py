"""Config flow for Curve Control integration."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN,
    CONF_BACKEND_URL,
    CONF_HOME_SIZE,
    CONF_TARGET_TEMP,
    CONF_LOCATION,
    CONF_TIME_AWAY,
    CONF_TIME_HOME,
    CONF_SAVINGS_LEVEL,
    CONF_THERMOSTAT_ENTITY,
    CONF_WEATHER_ENTITY,
    DEFAULT_BACKEND_URL,
    DEFAULT_HOME_SIZE,
    DEFAULT_TARGET_TEMP,
    DEFAULT_LOCATION,
    DEFAULT_TIME_AWAY,
    DEFAULT_TIME_HOME,
    DEFAULT_SAVINGS_LEVEL,
    LOCATIONS,
    SAVINGS_LEVELS,
)

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    session = async_get_clientsession(hass)
    
    # Test connection to backend
    backend_url = data.get(CONF_BACKEND_URL, DEFAULT_BACKEND_URL)
    
    try:
        # Prepare test request
        test_data = {
            "homeSize": data[CONF_HOME_SIZE],
            "homeTemperature": data[CONF_TARGET_TEMP],
            "location": int(data[CONF_LOCATION]),
            "timeAway": data[CONF_TIME_AWAY],
            "timeHome": data[CONF_TIME_HOME],
            "savingsLevel": int(data[CONF_SAVINGS_LEVEL]),
        }
        
        async with session.post(
            f"{backend_url}/generate_schedule",
            json=test_data,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as response:
            if response.status != 200:
                raise CannotConnect(f"Backend returned status {response.status}")
            
            result = await response.json()
            if "HourlyTemperature" not in result:
                raise InvalidResponse("Backend response missing required data")
    
    except aiohttp.ClientError as err:
        raise CannotConnect(f"Failed to connect to backend: {err}")
    except Exception as err:
        _LOGGER.exception("Unexpected exception")
        raise InvalidResponse(f"Unexpected error: {err}")
    
    # Return info that you want to store in the config entry
    # Convert location to int since form sends it as string
    location_key = int(data[CONF_LOCATION])
    return {"title": f"Curve Control - {LOCATIONS[location_key]}"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Curve Control."""
    
    VERSION = 1
    
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                
                # Create unique ID based on location and thermostat
                unique_id = f"{user_input[CONF_LOCATION]}_{user_input.get(CONF_THERMOSTAT_ENTITY, 'default')}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                
                return self.async_create_entry(title=info["title"], data=user_input)
            
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidResponse:
                errors["base"] = "invalid_response"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
        
        # Get list of climate entities for thermostat selection
        climate_entities = [
            state.entity_id
            for state in self.hass.states.async_all("climate")
        ]
        
        # Get list of weather entities
        weather_entities = [
            state.entity_id
            for state in self.hass.states.async_all("weather")
        ]
        
        # Build location options
        location_options = [
            selector.SelectOptionDict(value=str(k), label=v)
            for k, v in LOCATIONS.items()
        ]
        
        # Build savings level options
        savings_options = [
            selector.SelectOptionDict(value=str(k), label=v)
            for k, v in SAVINGS_LEVELS.items()
        ]
        
        # Create the form schema
        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_THERMOSTAT_ENTITY,
                    default=climate_entities[0] if climate_entities else None,
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="climate")
                ),
                vol.Required(
                    CONF_HOME_SIZE,
                    default=DEFAULT_HOME_SIZE,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=500,
                        max=10000,
                        step=100,
                        unit_of_measurement="sq ft",
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_TARGET_TEMP,
                    default=DEFAULT_TARGET_TEMP,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=60,
                        max=85,
                        step=1,
                        unit_of_measurement="°F",
                        mode=selector.NumberSelectorMode.SLIDER,
                    )
                ),
                vol.Required(
                    CONF_LOCATION,
                    default=str(DEFAULT_LOCATION),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=location_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    CONF_TIME_AWAY,
                    default=DEFAULT_TIME_AWAY,
                ): selector.TimeSelector(),
                vol.Required(
                    CONF_TIME_HOME,
                    default=DEFAULT_TIME_HOME,
                ): selector.TimeSelector(),
                vol.Required(
                    CONF_SAVINGS_LEVEL,
                    default=str(DEFAULT_SAVINGS_LEVEL),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=savings_options,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                ),
                vol.Optional(
                    CONF_WEATHER_ENTITY,
                    default=weather_entities[0] if weather_entities else None,
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="weather")
                ),
                vol.Optional(
                    CONF_BACKEND_URL,
                    default=DEFAULT_BACKEND_URL,
                ): str,
            }
        )
        
        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )
    
    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reconfiguration."""
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                
                # Update the config entry
                self.hass.config_entries.async_update_entry(
                    entry,
                    data=user_input,
                    title=info["title"],
                )
                
                # Trigger optimization with new preferences
                if DOMAIN in self.hass.data and entry.entry_id in self.hass.data[DOMAIN]:
                    coordinator = self.hass.data[DOMAIN][entry.entry_id]["coordinator"]
                    await coordinator.force_optimization()
                
                # Reload the integration
                await self.hass.config_entries.async_reload(entry.entry_id)
                
                return self.async_abort(reason="reconfigure_successful")
            
            except CannotConnect:
                errors = {"base": "cannot_connect"}
            except InvalidResponse:
                errors = {"base": "invalid_response"}
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors = {"base": "unknown"}
        else:
            user_input = entry.data
            errors = {}
        
        # Use the same schema as initial setup
        return await self.async_step_user(user_input)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidResponse(HomeAssistantError):
    """Error to indicate the response was invalid."""