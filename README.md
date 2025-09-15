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

## Dashboard Cards

### Basic Dashboard 

A basic layout shows automatically.

### Advanced Graph (Requires ApexCharts from HACS)

For an added visual for the temperature schedule, first install [ApexCharts Card](https://github.com/RomRider/apexcharts-card) via HACS, then add:

```yaml
type: custom:apexcharts-card
header:
  show: true
  title: Curve Control - Optimized Temperatures
graph_span: 24h
span:
  start: day
yaxis:
  - id: temp
    min: 0
    max: 100
    decimals: 1
    apex_config:
      title:
        text: Temperature (°F)
  - id: price
    opposite: true
    min: 0
    max: 1.5
    decimals: 1
    apex_config:
      title:
        text: Price ($/kWh)
series:
  - entity: sensor.curve_control_energy_optimizer_temperature_schedule_chart
    name: Target Temperature
    yaxis_id: temp
    data_generator: |
      const data = entity.attributes.graph_data;
      if (!data || !data.datasets) return [];
      const target = data.datasets[0].data;
      return target.map((temp, i) => {
        const hour = Math.floor(i / 2);
        const minute = (i % 2) * 30;
        const time = new Date();
        time.setHours(hour, minute, 0, 0);
        return [time.getTime(), temp];
      });
    type: line
    color: green
    stroke_width: 2
  - entity: sensor.curve_control_energy_optimizer_temperature_schedule_chart
    name: High Limit
    yaxis_id: temp
    data_generator: |
      const data = entity.attributes.graph_data;
      if (!data || !data.datasets) return [];
      const high = data.datasets[1].data;
      return high.map((temp, i) => {
        const hour = Math.floor(i / 2);
        const minute = (i % 2) * 30;
        const time = new Date();
        time.setHours(hour, minute, 0, 0);
        return [time.getTime(), temp];
      });
    type: line
    color: blue
    stroke_width: 2
    stroke_dash: 5
    opacity: 0.7
  - entity: sensor.curve_control_energy_optimizer_temperature_schedule_chart
    name: Low Limit
    yaxis_id: temp
    data_generator: |
      const data = entity.attributes.graph_data;
      if (!data || !data.datasets) return [];
      const low = data.datasets[2].data;
      return low.map((temp, i) => {
        const hour = Math.floor(i / 2);
        const minute = (i % 2) * 30;
        const time = new Date();
        time.setHours(hour, minute, 0, 0);
        return [time.getTime(), temp];
      });
    type: line
    color: blue
    stroke_width: 2
    stroke_dash: 5
    opacity: 0.7
  - entity: sensor.curve_control_energy_optimizer_temperature_schedule_chart
    name: Electricity Price
    yaxis_id: price
    data_generator: |
      const data = entity.attributes.graph_data;
      if (!data || !data.datasets) return [];
      const prices = data.datasets[3].data;
      return prices.map((price, i) => {
        const hour = Math.floor(i / 2);
        const minute = (i % 2) * 30;
        const time = new Date();
        time.setHours(hour, minute, 0, 0);
        return [time.getTime(), price];
      });
    type: area
    color: orange
    stroke_width: 2
    opacity: 0.3
```

### Interactive Custom Card (Optional)

For an advanced interactive card with settings controls and built-in graphs, search for **"Curve Control Card"** in HACS Frontend section (separate installation). Or pull from: https://github.com/boringbots/curve-control-card

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