# Curve Control Energy Optimizer for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

An advanced Home Assistant integration that optimizes your HVAC system based on time-of-use electricity rates to save money and reduce carbon emissions.

## Features

- 🏠 **Smart Thermostat Control** - Automatically adjusts temperatures based on electricity rates
- 💰 **Cost Savings** - Typically saves 10-25% on heating/cooling costs
- 🌱 **Environmental Impact** - Reduces CO2 emissions by shifting usage to off-peak hours
- 📊 **Real-time Monitoring** - Track savings, CO2 reduction, and optimization status
- ⚡ **Multiple Utility Rates** - Supports 7 major utility providers
- 🎯 **Comfort First** - Maintains your comfort preferences while optimizing
- 🔄 **Manual Override** - Toggle optimization on/off with a simple switch
- 📈 **Visual Schedule** - Graph showing 24-hour temperature schedule vs electricity prices

## Supported Utility Providers

- San Diego Gas & Electric (TOU-DR1, TOU-DR2, TOU-DR-P, TOU-ELEC, Standard DR)
- New Hampshire TOU Whole House Domestic
- Texas XCEL Time-Of-Use

## Installation

### Method 1: Manual Installation

1. Copy the `curve_control` folder to your `config/custom_components/` directory
2. Restart Home Assistant
3. Go to Settings → Devices & Services → Add Integration
4. Search for "Curve Control Energy Optimizer"

### Method 2: HACS (Recommended)

1. Open HACS in Home Assistant
2. Go to "Integrations"
3. Click the three dots menu → Custom repositories
4. Add this repository URL with category "Integration"
5. Install "Curve Control Energy Optimizer"
6. Restart Home Assistant

## Configuration

1. **Select Thermostat**: Choose your existing Home Assistant thermostat
2. **Home Details**: Enter your home size and preferred temperature
3. **Utility Plan**: Select your electricity provider and rate plan
4. **Schedule**: Set your typical away and home times
5. **Savings Level**: Choose optimization aggressiveness (Low/Medium/High)

## Entities Created

### Climate Entity
- `climate.curve_control_thermostat` - Optimized thermostat control

### Sensors
- `sensor.curve_control_savings` - Current cost savings ($)
- `sensor.curve_control_co2_avoided` - CO2 emissions avoided (metric tons)
- `sensor.curve_control_status` - Optimization status
- `sensor.curve_control_next_setpoint` - Next temperature target
- `sensor.curve_control_current_interval` - Current time interval
- `sensor.curve_control_temperature_schedule_chart` - Graph data for visualization

### Switches
- `switch.curve_control_use_optimized_temperatures` - Toggle optimization on/off

### Services
- `curve_control.update_schedule` - Update optimization parameters
- `curve_control.force_optimization` - Force immediate recalculation

## Dashboard

The integration automatically creates a custom dashboard card with:

- **Toggle Switch** - Enable/disable optimization with one click
- **Status Display** - Current savings and optimization status  
- **Temperature Graph** - Visual 24-hour schedule showing target temperatures vs electricity prices
- **Current Info** - Next setpoint and time period details

After installing the integration, you can add the Curve Control card to your dashboard:

1. Edit your dashboard
2. Click "Add Card"
3. Search for "Curve Control Card" 
4. Configure and add to your dashboard

The card will automatically update with your optimization schedule and provides full control over the system.

## Example Automation

```yaml
automation:
  - alias: "Update HVAC Schedule for Weekend"
    trigger:
      platform: time
      at: "06:00:00"
    condition:
      condition: time
      weekday:
        - sat
        - sun
    action:
      service: curve_control.update_schedule
      data:
        time_away: "10:00"
        time_home: "20:00"
        savings_level: 3
```

## How It Works

1. **Daily Optimization**: At midnight, the system automatically requests a new optimized schedule
2. **User Updates**: When you change preferences, optimization runs immediately
3. **Smart Control**: Every minute, the system checks and applies the optimal temperature
4. **Manual Override**: Use the toggle switch to disable optimization and control manually
5. **Visual Feedback**: The graph shows your 24-hour schedule aligned with electricity prices

## Backend Service

This integration uses a cloud-based optimization service hosted on Heroku. The service processes your temperature preferences and returns an optimized schedule. No personal data is stored - only anonymous usage patterns for optimization.

## Support

For issues, feature requests, or questions:
- Open an issue on GitHub
- Check the [documentation](https://github.com/curvecontrol/home-assistant-integration)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This integration is provided as-is. Always monitor your HVAC system and ensure proper operation. The developers are not responsible for any damage or excessive energy costs that may result from using this integration.