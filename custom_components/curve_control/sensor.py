"""Sensor platform for Curve Control integration."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import CurveControlCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Curve Control sensor entities from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    
    sensors = [
        CurveControlSavingsSensor(coordinator, entry),
        CurveControlCO2Sensor(coordinator, entry),
        CurveControlStatusSensor(coordinator, entry),
        CurveControlNextSetpointSensor(coordinator, entry),
        CurveControlCurrentIntervalSensor(coordinator, entry),
    ]
    
    async_add_entities(sensors, True)


class CurveControlBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for Curve Control sensors."""
    
    _attr_has_entity_name = True
    
    def __init__(
        self,
        coordinator: CurveControlCoordinator,
        entry: ConfigEntry,
        sensor_type: str,
        name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{sensor_type}"
        self._attr_name = name
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Curve Control Energy Optimizer",
            "manufacturer": "Curve Control",
            "model": "Energy Optimizer v1.0",
        }


class CurveControlSavingsSensor(CurveControlBaseSensor):
    """Sensor for energy savings information."""
    
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "$"
    _attr_icon = "mdi:piggy-bank"
    
    def __init__(self, coordinator: CurveControlCoordinator, entry: ConfigEntry) -> None:
        """Initialize the savings sensor."""
        super().__init__(coordinator, entry, "savings", "Energy Savings")
    
    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self.coordinator.optimization_results:
            return self.coordinator.optimization_results.get("costSavings", 0)
        return None
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        attrs = {}
        
        if self.coordinator.optimization_results:
            results = self.coordinator.optimization_results
            attrs["percent_savings"] = f"{results.get('percentSavings', 0)}%"
            attrs["calculation_period"] = "120 days"
            attrs["last_updated"] = datetime.now().isoformat()
        
        return attrs


class CurveControlCO2Sensor(CurveControlBaseSensor):
    """Sensor for CO2 emissions avoided."""
    
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "metric tons"
    _attr_icon = "mdi:molecule-co2"
    
    def __init__(self, coordinator: CurveControlCoordinator, entry: ConfigEntry) -> None:
        """Initialize the CO2 sensor."""
        super().__init__(coordinator, entry, "co2_avoided", "CO2 Avoided")
    
    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self.coordinator.optimization_results:
            return self.coordinator.optimization_results.get("co2Avoided", 0)
        return None
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        attrs = {}
        
        if self.coordinator.optimization_results:
            results = self.coordinator.optimization_results
            attrs["cars_equivalent"] = f"{results.get('carsEquivalent', 0)} cars"
            attrs["calculation_period"] = "120 days"
        
        return attrs


class CurveControlStatusSensor(CurveControlBaseSensor):
    """Sensor for optimization status."""
    
    _attr_icon = "mdi:chart-line"
    
    def __init__(self, coordinator: CurveControlCoordinator, entry: ConfigEntry) -> None:
        """Initialize the status sensor."""
        super().__init__(coordinator, entry, "status", "Optimization Status")
    
    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        if self.coordinator.optimization_results:
            return "Optimized"
        elif self.coordinator.last_update_success:
            return "Active"
        else:
            return "Pending"
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        attrs = {
            "last_update": self.coordinator.last_update_success_time.isoformat() if self.coordinator.last_update_success_time else None,
            "update_success": self.coordinator.last_update_success,
        }
        
        if self.coordinator.optimization_results:
            # Add timing information
            from datetime import datetime
            now = datetime.now()
            interval = (now.hour * 2) + (now.minute // 30)
            
            attrs["current_30min_interval"] = interval
            attrs["intervals_per_day"] = 48
            attrs["heat_up_rate"] = f"{self.coordinator.heat_up_rate}°F/30min"
            attrs["cool_down_rate"] = f"{self.coordinator.cool_down_rate}°F/30min"
        
        return attrs


class CurveControlNextSetpointSensor(CurveControlBaseSensor):
    """Sensor for next temperature setpoint."""
    
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT
    _attr_icon = "mdi:thermometer"
    
    def __init__(self, coordinator: CurveControlCoordinator, entry: ConfigEntry) -> None:
        """Initialize the next setpoint sensor."""
        super().__init__(coordinator, entry, "next_setpoint", "Next Temperature Setpoint")
    
    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self.coordinator.get_current_setpoint()
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        attrs = {}
        
        bounds = self.coordinator.get_schedule_bounds()
        if bounds:
            # Get current and next intervals
            from datetime import datetime
            now = datetime.now()
            current_interval = (now.hour * 2) + (now.minute // 30)
            next_interval = (current_interval + 1) % 48
            
            if 0 <= current_interval < len(bounds[0]):
                attrs["current_high_bound"] = bounds[0][current_interval]
                attrs["current_low_bound"] = bounds[1][current_interval]
            
            if 0 <= next_interval < len(bounds[0]):
                attrs["next_high_bound"] = bounds[0][next_interval]
                attrs["next_low_bound"] = bounds[1][next_interval]
                
                # Calculate time until next interval
                minutes_until_next = 30 - (now.minute % 30)
                attrs["minutes_until_next_interval"] = minutes_until_next
        
        return attrs


class CurveControlCurrentIntervalSensor(CurveControlBaseSensor):
    """Sensor for current time interval."""
    
    _attr_icon = "mdi:clock-outline"
    
    def __init__(self, coordinator: CurveControlCoordinator, entry: ConfigEntry) -> None:
        """Initialize the current interval sensor."""
        super().__init__(coordinator, entry, "current_interval", "Current Time Interval")
    
    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        from datetime import datetime
        now = datetime.now()
        interval = (now.hour * 2) + (now.minute // 30)
        
        # Format as time range
        start_hour = interval // 2
        start_min = (interval % 2) * 30
        end_hour = (interval + 1) // 2
        end_min = ((interval + 1) % 2) * 30
        
        if end_hour == 24:
            end_hour = 0
        
        return f"{start_hour:02d}:{start_min:02d} - {end_hour:02d}:{end_min:02d}"
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        from datetime import datetime
        now = datetime.now()
        interval = (now.hour * 2) + (now.minute // 30)
        
        attrs = {
            "interval_number": interval + 1,  # 1-indexed for display
            "total_intervals": 48,
            "minutes_into_interval": now.minute % 30,
            "minutes_remaining": 30 - (now.minute % 30),
        }
        
        # Add price information if available
        if self.coordinator.config:
            location = self.coordinator.config.get("location", 1)
            # This would need to be expanded with actual price data
            attrs["rate_period"] = self._get_rate_period(interval, location)
        
        return attrs
    
    def _get_rate_period(self, interval: int, location: int) -> str:
        """Determine the rate period based on interval and location."""
        # This is a simplified version - would need full rate schedule
        hour = interval // 2
        
        # Example for location 1 (SDG&E TOU-DR1)
        if location == 1:
            if 16 <= hour < 21:  # 4pm - 9pm
                return "On-Peak"
            elif 6 <= hour < 16 or 21 <= hour < 24:  # 6am-4pm, 9pm-12am
                return "Off-Peak"
            else:  # 12am - 6am
                return "Super Off-Peak"
        
        return "Standard"