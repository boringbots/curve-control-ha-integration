"""The Curve Control Energy Optimizer integration."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

import aiohttp
import async_timeout
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

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
    DEFAULT_BACKEND_URL,
    UPDATE_INTERVAL,
    INTERVALS_PER_DAY,
    COOL_30MIN,
    HEAT_30MIN,
    DEADBAND_OFFSET,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.CLIMATE, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Curve Control from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    # Create the data coordinator
    coordinator = CurveControlCoordinator(hass, entry)
    
    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()
    
    # Store coordinator
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "config": entry.data,
    }
    
    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Register services
    async def handle_update_schedule(call):
        """Handle schedule update service call."""
        await coordinator.async_update_schedule(call.data)
    
    hass.services.async_register(
        DOMAIN,
        "update_schedule",
        handle_update_schedule,
    )
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok


class CurveControlCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Curve Control data from backend."""
    
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        self.hass = hass
        self.entry = entry
        self.backend_url = entry.data.get(CONF_BACKEND_URL, DEFAULT_BACKEND_URL)
        self.session = async_get_clientsession(hass)
        
        # Store configuration
        self.config = {
            "homeSize": entry.data[CONF_HOME_SIZE],
            "homeTemperature": entry.data[CONF_TARGET_TEMP],
            "location": entry.data[CONF_LOCATION],
            "timeAway": entry.data[CONF_TIME_AWAY],
            "timeHome": entry.data[CONF_TIME_HOME],
            "savingsLevel": entry.data[CONF_SAVINGS_LEVEL],
        }
        
        # Initialize data storage
        self.schedule_data = None
        self.optimization_results = None
        self.heat_up_rate = HEAT_30MIN  # Default value for 30-min intervals
        self.cool_down_rate = COOL_30MIN  # Default value for 30-min intervals
        
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=UPDATE_INTERVAL),
        )
    
    async def _async_update_data(self):
        """Fetch data from backend."""
        try:
            # Get current thermostat state if available
            thermostat_entity = self.entry.data.get(CONF_THERMOSTAT_ENTITY)
            if thermostat_entity:
                state = self.hass.states.get(thermostat_entity)
                if state:
                    current_temp = state.attributes.get("current_temperature")
                    if current_temp:
                        self.config["homeTemperature"] = current_temp
            
            # Generate 30-minute temperature schedule
            schedule_data = self._build_30min_temperature_schedule()
            
            # Prepare request with schedule data
            request_data = {
                **self.config,
                "temperatureSchedule": schedule_data,
                "heatUpRate": self.heat_up_rate,
                "coolDownRate": self.cool_down_rate,
            }
            
            # Call backend for optimization
            async with async_timeout.timeout(30):
                response = await self.session.post(
                    f"{self.backend_url}/generate_schedule",
                    json=request_data,
                )
                response.raise_for_status()
                data = await response.json()
                
                # Store the results
                self.optimization_results = data
                self.schedule_data = data.get("HourlyTemperature", [])
                
                return data
                
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error communicating with backend: {err}")
        except Exception as err:
            raise UpdateFailed(f"Unexpected error: {err}")
    
    async def async_update_schedule(self, data: dict[str, Any]) -> None:
        """Update the schedule configuration."""
        # Update configuration
        if "homeSize" in data:
            self.config["homeSize"] = data["homeSize"]
        if "savingsLevel" in data:
            self.config["savingsLevel"] = data["savingsLevel"]
        if "timeAway" in data:
            self.config["timeAway"] = data["timeAway"]
        if "timeHome" in data:
            self.config["timeHome"] = data["timeHome"]
        
        # Request refresh
        await self.async_request_refresh()
    
    def _build_30min_temperature_schedule(self) -> dict:
        """Build 30-minute temperature schedule to send to backend."""
        from datetime import datetime, time
        
        base_temp = self.config["homeTemperature"]
        away_time = self.config["timeAway"]
        home_time = self.config["timeHome"]
        savings_level = self.config["savingsLevel"]
        
        # Convert times to 30-minute intervals
        away_interval = self._time_to_30min_index(away_time)
        home_interval = self._time_to_30min_index(home_time)
        
        # Calculate temperature offsets based on savings level
        savings_offset = self._calculate_savings_offset(savings_level)
        
        high_temps = []
        low_temps = []
        
        for interval in range(INTERVALS_PER_DAY):
            if away_interval <= interval <= home_interval:
                # Away period - allow more temperature variation for savings
                high_temps.append(base_temp + savings_offset + DEADBAND_OFFSET)
                low_temps.append(base_temp - savings_offset - DEADBAND_OFFSET)
            else:
                # Home period - tighter comfort range
                high_temps.append(base_temp + DEADBAND_OFFSET)
                low_temps.append(base_temp - DEADBAND_OFFSET)
        
        return {
            "highTemperatures": high_temps,
            "lowTemperatures": low_temps,
            "intervalMinutes": 30,
            "totalIntervals": INTERVALS_PER_DAY
        }
    
    def _time_to_30min_index(self, time_str: str) -> int:
        """Convert time string to 30-minute interval index (0-47)."""
        try:
            from datetime import datetime
            time_obj = datetime.strptime(time_str, "%H:%M")
            total_minutes = time_obj.hour * 60 + time_obj.minute
            return total_minutes // 30
        except (ValueError, AttributeError):
            return 16  # Default to 8:00 AM
    
    def _calculate_savings_offset(self, savings_level: int) -> float:
        """Convert savings level to temperature offset."""
        savings_map = {1: 2, 2: 6, 3: 12}
        return savings_map.get(savings_level, 6)
    
    def get_current_setpoint(self) -> float | None:
        """Get the current temperature setpoint based on optimization."""
        if not self.optimization_results:
            return None
        
        best_temps = self.optimization_results.get("bestTempActual", [])
        if not best_temps:
            return None
        
        # Get current 30-minute interval
        from datetime import datetime
        now = datetime.now()
        interval = (now.hour * 2) + (now.minute // 30)
        
        if 0 <= interval < len(best_temps):
            return best_temps[interval]
        
        return None
    
    def get_schedule_bounds(self) -> tuple[list, list] | None:
        """Get the high and low temperature bounds for the current schedule."""
        if not self.schedule_data or len(self.schedule_data) < 3:
            return None
        
        return (self.schedule_data[1], self.schedule_data[2])  # high, low bounds