# Curve Control Energy Optimizer for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

An advanced Home Assistant integration that optimizes your HVAC system based on time-of-use electricity rates to save money and reduce carbon emissions.

## Features

- **Smart Thermostat Control** - Automatically adjusts temperatures based on electricity rates
- **Cost Savings** - Typically saves 10-25% on heating/cooling costs
- **Environmental Impact** - Reduces CO2 emissions by shifting usage to off-peak hours
- **Real-time Monitoring** - Track savings, CO2 reduction, and optimization status
- **Multiple Utility Rates** - Supports 7 major utility providers
- **Comfort First** - Maintains your comfort preferences while optimizing
- **Manual Override** - Toggle optimization on/off with a simple switch
- **Visual Schedule** - Graph showing 24-hour temperature schedule vs electricity prices

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

## Dashboard Options

### Option 1: Custom Interactive Card (Advanced)

For the full interactive experience with settings controls, you can install the custom JavaScript card:

1. Copy `custom_components/curve_control/curve-control-card.js` to `config/www/curve_control/curve-control-card.js`
2. Go to Settings → Dashboards → Resources
3. Add resource: `/local/curve_control/curve-control-card.js` (Type: JavaScript Module)
4. Edit your dashboard and search for "Curve Control Card"

The custom card includes:
- **Toggle Switch** - Enable/disable optimization with one click
- **Status Display** - Current savings and optimization status  
- **Temperature Graph** - Visual 24-hour schedule vs electricity prices
- **Settings Tabs** - Basic and detailed schedule configuration

### Option 2: Simple Copy-Paste Card (Recommended)

Create a dashboard card instantly by copying this YAML code:

```yaml
type: vertical-stack
cards:
  - type: entities
    title: Curve Control Energy Optimizer
    entities:
      - entity: switch.curve_control_use_optimized_temperatures
        name: Use Optimized Schedule
        icon: mdi:thermostat-auto
      - type: divider
      - entity: sensor.curve_control_status
        name: Status
        icon: mdi:information-outline
      - entity: sensor.curve_control_savings
        name: Daily Savings
        icon: mdi:currency-usd
      - entity: sensor.curve_control_co2_avoided
        name: CO2 Avoided
        icon: mdi:leaf
      - entity: sensor.curve_control_next_setpoint
        name: Next Temperature
        icon: mdi:thermometer
      - entity: sensor.curve_control_current_interval
        name: Current Interval
        icon: mdi:clock-outline
  - type: conditional
    conditions:
      - entity: sensor.curve_control_temperature_schedule_chart
        state_not: unavailable
    card:
      type: custom:apexcharts-card
      header:
        show: true
        title: Temperature Schedule vs Electricity Prices
      graph_span: 24h
      span:
        start: day
      yaxis:
        - id: temperature
          min: 65
          max: 80
          apex_config:
            title:
              text: Temperature (°F)
        - id: price
          opposite: true
          min: 0
          max: 0.6
          apex_config:
            title:
              text: Price ($/kWh)
      series:
        - entity: sensor.curve_control_temperature_schedule_chart
          attribute: target_temperatures
          name: Target Temperature
          type: line
          color: '#4CAF50'
          stroke_width: 3
          yaxis_id: temperature
        - entity: sensor.curve_control_temperature_schedule_chart
          attribute: high_limits
          name: High Limit
          type: line
          color: '#FF6384'
          stroke_width: 2
          stroke_dasharray: 5
          yaxis_id: temperature
        - entity: sensor.curve_control_temperature_schedule_chart
          attribute: low_limits
          name: Low Limit
          type: line
          color: '#36A2EB'
          stroke_width: 2
          stroke_dasharray: 5
          yaxis_id: temperature
        - entity: sensor.curve_control_temperature_schedule_chart
          attribute: electricity_prices
          name: Electricity Price
          type: column
          color: '#FF9800'
          opacity: 0.3
          yaxis_id: price
```

**Note**: This manual card requires the [ApexCharts Card](https://github.com/RomRider/apexcharts-card) from HACS for the temperature schedule graph. If you don't have ApexCharts installed, remove the conditional card section and use only the entities card.

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