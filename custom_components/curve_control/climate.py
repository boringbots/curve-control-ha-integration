"""Climate platform for Curve Control integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import CurveControlCoordinator
from .const import (
    DOMAIN,
    CONF_THERMOSTAT_ENTITY,
    ATTR_SCHEDULE_HIGH,
    ATTR_SCHEDULE_LOW,
    ATTR_BEST_TEMP_ACTUAL,
    ATTR_OPTIMIZATION_STATUS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Curve Control climate entity from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    
    # Get the original thermostat entity if configured
    thermostat_entity_id = entry.data.get(CONF_THERMOSTAT_ENTITY)
    
    async_add_entities(
        [CurveControlThermostat(coordinator, entry, thermostat_entity_id)],
        True,
    )


class CurveControlThermostat(CoordinatorEntity, ClimateEntity):
    """Representation of a Curve Control optimized thermostat."""
    
    _attr_has_entity_name = True
    _attr_name = "Optimized Thermostat"
    _attr_temperature_unit = UnitOfTemperature.FAHRENHEIT
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.COOL, HVACMode.HEAT_COOL]
    
    def __init__(
        self,
        coordinator: CurveControlCoordinator,
        entry: ConfigEntry,
        thermostat_entity_id: str | None,
    ) -> None:
        """Initialize the thermostat."""
        super().__init__(coordinator)
        
        self._entry = entry
        self._thermostat_entity_id = thermostat_entity_id
        self._attr_unique_id = f"{entry.entry_id}_climate"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Curve Control Energy Optimizer",
            "manufacturer": "Curve Control",
            "model": "Energy Optimizer v1.0",
        }
        
        # Internal state
        self._hvac_mode = HVACMode.HEAT_COOL
        self._target_temperature = None
        self._current_temperature = None
        self._hvac_action = HVACAction.IDLE
        
        # We'll sync with thermostat after entity is added to hass
    
    @callback
    def _sync_with_thermostat(self) -> None:
        """Sync state with the linked thermostat."""
        if not self._thermostat_entity_id:
            return
        
        state = self.hass.states.get(self._thermostat_entity_id)
        if state:
            # Get current temperature
            self._current_temperature = state.attributes.get("current_temperature")
            
            # Map HVAC mode
            if state.state == "off":
                self._hvac_mode = HVACMode.OFF
            elif state.state == "cool":
                self._hvac_mode = HVACMode.COOL
            elif state.state == "heat":
                self._hvac_mode = HVACMode.HEAT
            elif state.state in ["heat_cool", "auto"]:
                self._hvac_mode = HVACMode.HEAT_COOL
            
            # Get HVAC action
            hvac_action = state.attributes.get("hvac_action")
            if hvac_action == "cooling":
                self._hvac_action = HVACAction.COOLING
            elif hvac_action == "heating":
                self._hvac_action = HVACAction.HEATING
            elif hvac_action == "idle":
                self._hvac_action = HVACAction.IDLE
            elif hvac_action == "off":
                self._hvac_action = HVACAction.OFF
    
    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        await super().async_added_to_hass()
        
        # Now sync with thermostat since hass is available
        if self._thermostat_entity_id:
            self._sync_with_thermostat()
    
    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        # Try to get from linked thermostat first
        if self._thermostat_entity_id:
            state = self.hass.states.get(self._thermostat_entity_id)
            if state and state.attributes.get("current_temperature"):
                return state.attributes.get("current_temperature")
        
        return self._current_temperature
    
    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        # Get optimized setpoint from coordinator
        setpoint = self.coordinator.get_current_setpoint()
        if setpoint:
            return setpoint
        
        # Fall back to manual target or linked thermostat
        if self._target_temperature:
            return self._target_temperature
        
        if self._thermostat_entity_id:
            state = self.hass.states.get(self._thermostat_entity_id)
            if state and state.attributes.get("temperature"):
                return state.attributes.get("temperature")
        
        return None
    
    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation mode."""
        return self._hvac_mode
    
    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current running hvac operation."""
        return self._hvac_action
    
    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return 60
    
    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return 85
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        attrs = {}
        
        # Add optimization data if available
        if self.coordinator.optimization_results:
            results = self.coordinator.optimization_results
            attrs[ATTR_OPTIMIZATION_STATUS] = "optimized"
            attrs["cost_savings"] = f"${results.get('costSavings', 0)}"
            attrs["percent_savings"] = f"{results.get('percentSavings', 0)}%"
            attrs["co2_avoided"] = f"{results.get('co2Avoided', 0)} metric tons"
            
            # Add schedule bounds
            bounds = self.coordinator.get_schedule_bounds()
            if bounds:
                # Get current interval
                from datetime import datetime
                now = datetime.now()
                interval = (now.hour * 2) + (now.minute // 30)
                
                if 0 <= interval < len(bounds[0]):
                    attrs[ATTR_SCHEDULE_HIGH] = bounds[0][interval]
                    attrs[ATTR_SCHEDULE_LOW] = bounds[1][interval]
            
            # Add best temperature profile
            if "bestTempActual" in results:
                attrs[ATTR_BEST_TEMP_ACTUAL] = results["bestTempActual"]
        else:
            attrs[ATTR_OPTIMIZATION_STATUS] = "pending"
        
        # Add linked thermostat info
        if self._thermostat_entity_id:
            attrs["linked_thermostat"] = self._thermostat_entity_id
        
        return attrs
    
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        
        self._target_temperature = temperature
        
        # If we have a linked thermostat, update it
        if self._thermostat_entity_id:
            await self.hass.services.async_call(
                "climate",
                "set_temperature",
                {
                    "entity_id": self._thermostat_entity_id,
                    ATTR_TEMPERATURE: temperature,
                },
                blocking=False,
            )
        
        self.async_write_ha_state()
    
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        self._hvac_mode = hvac_mode
        
        # If we have a linked thermostat, update it
        if self._thermostat_entity_id:
            # Map our mode to the thermostat's mode
            thermostat_mode = hvac_mode
            if hvac_mode == HVACMode.HEAT_COOL:
                # Check if the thermostat supports heat_cool or auto
                state = self.hass.states.get(self._thermostat_entity_id)
                if state and "heat_cool" not in state.attributes.get("hvac_modes", []):
                    thermostat_mode = "auto" if "auto" in state.attributes.get("hvac_modes", []) else "cool"
            
            await self.hass.services.async_call(
                "climate",
                "set_hvac_mode",
                {
                    "entity_id": self._thermostat_entity_id,
                    "hvac_mode": thermostat_mode,
                },
                blocking=False,
            )
        
        self.async_write_ha_state()
    
    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        await self.async_set_hvac_mode(HVACMode.HEAT_COOL)
    
    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        await self.async_set_hvac_mode(HVACMode.OFF)
    
    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Update target temperature from optimization
        if self.coordinator.get_current_setpoint():
            new_setpoint = self.coordinator.get_current_setpoint()
            
            # If we have a linked thermostat and the setpoint changed, update it
            if self._thermostat_entity_id and new_setpoint != self._target_temperature:
                self.hass.async_create_task(
                    self.hass.services.async_call(
                        "climate",
                        "set_temperature",
                        {
                            "entity_id": self._thermostat_entity_id,
                            ATTR_TEMPERATURE: new_setpoint,
                        },
                        blocking=False,
                    )
                )
        
        # Sync with linked thermostat
        self._sync_with_thermostat()
        
        self.async_write_ha_state()