"""The Curve Control Energy Optimizer integration."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any
import os

import aiohttp
import async_timeout
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.components import frontend

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
    INTERVALS_PER_DAY,
    COOL_30MIN,
    HEAT_30MIN,
    DEADBAND_OFFSET,
)
from .thermal_learning import ThermalLearningManager

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.CLIMATE, Platform.SENSOR, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Curve Control from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    # Register custom card
    await async_register_custom_card(hass)
    
    # Create the data coordinator
    coordinator = CurveControlCoordinator(hass, entry)
    
    # Set up thermal learning if thermostat is configured
    if coordinator.thermal_learning:
        await coordinator.thermal_learning.async_setup()
    
    # Add delay to allow backend processing time before first optimization
    import asyncio
    _LOGGER.info("Calculating optimal temperature schedule...")
    await asyncio.sleep(10)
    
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
    
    async def handle_force_optimization(call):
        """Handle force optimization service call."""
        await coordinator.force_optimization()
    
    hass.services.async_register(
        DOMAIN,
        "update_schedule",
        handle_update_schedule,
    )
    
    hass.services.async_register(
        DOMAIN,
        "force_optimization",
        handle_force_optimization,
    )
    
    return True


async def async_register_custom_card(hass: HomeAssistant) -> None:
    """Provide instructions for custom card installation."""
    try:
        import pathlib
        integration_dir = pathlib.Path(__file__).parent
        
        # Check if user has already installed the card
        user_card_path = pathlib.Path(hass.config.path("www", "curve_control", "curve-control-card.js"))
        
        if user_card_path.exists():
            _LOGGER.info("✅ Custom card found at: /local/curve_control/curve-control-card.js")
            _LOGGER.info("🔧 Add this card to your dashboard with type: custom:curve-control-card")
        else:
            # Provide installation instructions
            _LOGGER.info("📋 CUSTOM CARD INSTALLATION REQUIRED:")
            _LOGGER.info("1️⃣  Create directory: config/www/curve_control/")
            _LOGGER.info("2️⃣  Copy curve-control-card.js from the integration to that directory")
            _LOGGER.info("3️⃣  Add this resource to Settings > Dashboards > Resources:")
            _LOGGER.info("     URL: /local/curve_control/curve-control-card.js")
            _LOGGER.info("     Type: JavaScript Module")
            _LOGGER.info("4️⃣  Add card to dashboard with type: custom:curve-control-card")
            
            # Check if the card file exists in integration directory
            integration_card_path = integration_dir / "curve-control-card.js"
            if integration_card_path.exists():
                _LOGGER.info(f"💡 Card source file available at: {integration_card_path}")
            else:
                _LOGGER.warning("⚠️  Card source file not found in integration directory")
            
    except Exception as err:
        _LOGGER.warning(f"Error checking custom card setup: {err}")



async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Clean up thermal learning
    data = hass.data[DOMAIN].get(entry.entry_id)
    if data:
        coordinator = data.get("coordinator")
        if coordinator and coordinator.thermal_learning:
            await coordinator.thermal_learning.async_cleanup()
    
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
            "timeAway": str(entry.data[CONF_TIME_AWAY])[:5],  # Convert HH:MM:SS to HH:MM
            "timeHome": str(entry.data[CONF_TIME_HOME])[:5],  # Convert HH:MM:SS to HH:MM
            "savingsLevel": entry.data[CONF_SAVINGS_LEVEL],
        }
        
        # Initialize data storage
        self.schedule_data = None
        self.optimization_results = None
        self.heat_up_rate = HEAT_30MIN  # Default value for 30-min intervals
        self.cool_down_rate = COOL_30MIN  # Default value for 30-min intervals
        
        # Initialize thermal learning
        self.thermal_learning = None
        thermostat_entity = entry.data.get(CONF_THERMOSTAT_ENTITY)
        if thermostat_entity:
            self.thermal_learning = ThermalLearningManager(hass, thermostat_entity)
        
        # Store daily schedule - no automatic polling
        self._daily_schedule = None
        self._schedule_date = None
        self._midnight_listener = None
        self._custom_temperature_schedule = None  # For detailed frontend schedules
        self.optimization_enabled = True  # Flag for optimization toggle
        
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=None,  # Disable automatic polling
        )
        
        # Set up midnight optimization
        self._setup_midnight_optimization()
    
    def _setup_midnight_optimization(self) -> None:
        """Set up automatic optimization at midnight."""
        import homeassistant.util.dt as dt_util
        from homeassistant.helpers.event import async_track_time_change
        
        # Schedule optimization at midnight every day
        self._midnight_listener = async_track_time_change(
            self.hass,
            self._handle_midnight_optimization,
            hour=0,
            minute=0,
            second=0,
        )
        _LOGGER.info("Scheduled daily optimization at midnight")
    
    async def _handle_midnight_optimization(self, now) -> None:
        """Handle midnight optimization trigger."""
        _LOGGER.info("Running scheduled midnight optimization")
        await self.async_request_refresh()
    
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
            
            # Update thermal rates from learning if available
            if self.thermal_learning:
                learned_heat_rate, learned_cool_rate = self.thermal_learning.get_thermal_rates_with_fallback()
                self.heat_up_rate = learned_heat_rate
                self.cool_down_rate = learned_cool_rate
                
                _LOGGER.debug(f"Using thermal rates - Heat: {self.heat_up_rate:.4f}, Cool: {self.cool_down_rate:.4f}")
            
            # Generate 30-minute temperature schedule (custom or basic)
            if self._custom_temperature_schedule:
                schedule_data = self._custom_temperature_schedule
                _LOGGER.info("Using custom temperature schedule from frontend")
            else:
                schedule_data = self._build_30min_temperature_schedule()
                _LOGGER.info("Using basic temperature schedule")
            
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
                
                # Validate response structure
                if not isinstance(data, dict):
                    raise ValueError("Backend returned invalid data format")
                
                # Store the results with validation
                self.optimization_results = data
                self.schedule_data = data.get("HourlyTemperature", [])
                
                # Store the daily schedule with date
                from datetime import datetime
                self._daily_schedule = data.get("bestTempActual", [])
                self._schedule_date = datetime.now().date()
                
                _LOGGER.info(f"Optimization complete. Received {len(self.schedule_data)} hourly temperatures and {len(self._daily_schedule)} daily setpoints")
                
                return data
                
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Backend communication error: {err}")
            raise UpdateFailed(f"Error communicating with backend: {err}")
        except Exception as err:
            _LOGGER.error(f"Coordinator optimization error: {err}")
            raise UpdateFailed(f"Unexpected error: {err}")
    
    async def async_update_schedule(self, data: dict[str, Any]) -> None:
        """Update the schedule configuration and trigger immediate optimization."""
        _LOGGER.info("User updated preferences - triggering optimization")
        
        # Update configuration from frontend data
        if "homeSize" in data:
            self.config["homeSize"] = data["homeSize"]
        if "homeTemperature" in data:
            self.config["homeTemperature"] = data["homeTemperature"]
        if "location" in data:
            self.config["location"] = data["location"]
        if "savingsLevel" in data:
            self.config["savingsLevel"] = data["savingsLevel"]
        if "timeAway" in data:
            # Ensure time is in HH:MM format - let it fail if format is wrong
            self.config["timeAway"] = str(data["timeAway"])[:5]
        if "timeHome" in data:
            # Ensure time is in HH:MM format - let it fail if format is wrong
            self.config["timeHome"] = str(data["timeHome"])[:5]
        
        # Store custom temperature schedule if provided (for detailed mode)
        if "temperatureSchedule" in data:
            self._custom_temperature_schedule = data["temperatureSchedule"]
            _LOGGER.info("Custom temperature schedule received from frontend")
        else:
            # Clear custom schedule for basic mode
            self._custom_temperature_schedule = None
        
        # Trigger immediate optimization
        await self.async_request_refresh()
    
    async def force_optimization(self) -> None:
        """Force immediate optimization."""
        _LOGGER.info("Forcing immediate optimization")
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
            # Handle both HH:MM and HH:MM:SS formats
            time_str = str(time_str)[:5]  # Ensure HH:MM format
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