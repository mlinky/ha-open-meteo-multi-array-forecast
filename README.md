# Multi-Array Solar Forecast Integration

A comprehensive Home Assistant integration for forecasting solar power generation across multiple solar arrays using the Open-Meteo weather API. This integration extends the capabilities of single-array solar forecasting to support complex solar installations with multiple arrays having different orientations, tilts, and capacities.

## Features

- **Multiple Solar Array Support**: Configure unlimited solar arrays with different specifications
- **Comprehensive Forecasting**: Get power and energy forecasts for individual arrays and system totals
- **Real-time Updates**: Automatic updates with configurable intervals
- **Detailed Metrics**: Current power, daily energy, peak power, and hourly forecasts
- **Weather Integration**: Incorporates temperature, cloud cover, and other weather factors
- **Service Integration**: Programmatic access to forecast data via Home Assistant services
- **Configuration Flow**: Easy setup through the Home Assistant UI

## Installation

### Manual Installation

1. Create a `multi_solar_forecast` directory in your `custom_components` folder
2. Copy all the integration files to this directory:
   ```
   custom_components/multi_solar_forecast/
   ├── __init__.py
   ├── config_flow.py
   ├── const.py
   ├── coordinator.py
   ├── manifest.json
   ├── sensor.py
   └── services.yaml
   ```
3. Restart Home Assistant
4. Go to Settings > Integrations > Add Integration
5. Search for "Multi-Array Solar Forecast"

### HACS Installation (Future)

This integration will be available through HACS once published.

## Configuration

### Initial Setup

1. **Location Configuration**: 
   - Latitude and longitude (defaults to your Home Assistant location)

2. **Solar Array Configuration**:
   For each solar array, you'll need to configure:
   - **Name**: Unique identifier for the array (e.g., "South Roof", "Carport")
   - **Declination**: Panel tilt angle in degrees (0° = horizontal, 90° = vertical)
   - **Azimuth**: Panel orientation in degrees (0° = North, 90° = East, 180° = South, 270° = West)
   - **kWp**: Peak power capacity in kilowatts
   - **Damping**: System losses factor (0.0 = no losses, 1.0 = 100% losses)
   - **Horizon**: Optional horizon profile (future feature)

### Example Configurations

#### Single South-Facing Array
```
Name: Main Roof
Declination: 30°
Azimuth: 180°
kWp: 8.5
Damping: 0.15
```

#### Multiple Arrays System
```
Array 1 - South Roof:
- Declination: 35°, Azimuth: 180°, kWp: 6.0, Damping: 0.1

Array 2 - East Roof:
- Declination: 30°, Azimuth: 90°, kWp: 4.0, Damping: 0.15

Array 3 - Carport:
- Declination: 10°, Azimuth: 225°, kWp: 3.5, Damping: 0.2
```

## Entities Created

### Per Solar Array
Each configured array creates the following sensors:
- `sensor.{array_name}_current_power` - Current power output (kW)
- `sensor.{array_name}_today_energy` - Today's energy production (kWh)
- `sensor.{array_name}_tomorrow_energy` - Tomorrow's predicted energy (kWh)
- `sensor.{array_name}_peak_power_today` - Today's peak power (kW)
- `sensor.{array_name}_peak_power_tomorrow` - Tomorrow's predicted peak power (kW)

### System Totals
- `sensor.total_solar_current_power` - Combined current power from all arrays
- `sensor.total_solar_today_energy` - Combined today's energy from all arrays
- `sensor.total_solar_tomorrow_energy` - Combined tomorrow's energy from all arrays
- `sensor.total_solar_peak_power_today` - Combined today's peak power
- `sensor.total_solar_peak_power_tomorrow` - Combined tomorrow's peak power

## Services

### `multi_solar_forecast.update_forecast`
Manually trigger a forecast update.

**Parameters:**
- `entry_id` (optional): Specific configuration entry to update

**Example:**
```yaml
service: multi_solar_forecast.update_forecast
```

### `multi_solar_forecast.get_hourly_forecast`
Retrieve detailed hourly forecast data.

**Parameters:**
- `entry_id` (required): Configuration entry ID
- `array_name` (optional): Specific array name, omit for combined data
- `days` (optional): Number of forecast days (1-7, default: 1)

**Example:**
```yaml
service: multi_solar_forecast.get_hourly_forecast
data:
  entry_id: "your_entry_id"
  array_name: "South Roof"
  days: 3
```

## Sensor Attributes

### Individual Array Sensors
Each sensor includes attributes with:
- Array configuration (kWp, declination, azimuth, damping)
- 24-hour forecast data (for power sensors)
- Last update timestamp

### Total System Sensors
Total sensors include:
- Number of configured arrays
- Number of arrays with current data
- Individual array contributions
- Combined forecast data
- Total system capacity

## Automation Examples

### Daily Energy Report
```yaml
automation:
  - alias: "Solar Daily Report"
    trigger:
      - platform: time
        at: "20:00:00"
    action:
      - service: notify.mobile_app
        data:
          title: "Solar Production Report"
          message: >
            Today: {{ states('sensor.total_solar_today_energy') }}kWh
            Tomorrow forecast: {{ states('sensor.total_solar_tomorrow_energy') }}kWh
```

### Low Production Alert
```yaml
automation:
  - alias: "Low Solar Production Alert"
    trigger:
      - platform: numeric_state
        entity_id: sensor.total_solar_current_power
        below: 1.0
        for: "01:00:00"
    condition:
      - condition: sun
        after: sunrise
        after_offset: "02:00:00"
      - condition: sun
        before: sunset
        before_offset: "-02:00:00"
    action:
      - service: notify.homeowner
        data:
          message: "Solar production is unusually low. Check for issues."
```

### Peak Power Notification
```yaml
automation:
  - alias: "Solar Peak Power Achieved"
    trigger:
      - platform: template
        value_template: >
          {{ states('sensor.total_solar_current_power')|float >= 
             states('sensor.total_solar_peak_power_today')|float * 0.95 }}
    action:
      - service: notify.mobile_app
        data:
          message: >
            Solar system hitting peak performance: 
            {{ states('sensor.total_solar_current_power') }}kW
```

## Dashboard Cards

### Power Production Card
```yaml
type: entities
title: Solar Power Production
entities:
  - entity: sensor.total_solar_current_power
    name: Current Power
  - entity: sensor.total_solar_today_energy
    name: Today's Energy
  - entity: sensor.total_solar_tomorrow_energy
    name: Tomorrow Forecast
```

### Individual Arrays Card
```yaml
type: grid
cards:
  - type: entity
    entity: sensor.south_roof_current_power
    name: South Roof
  - type: entity
    entity: sensor.east_roof_current_power
    name: East Roof
  - type: entity
    entity: sensor.carport_current_power
    name: Carport
```

### Forecast Graph
```yaml
type: custom:apexcharts-card
header:
  title: Solar Forecast
graph_span: 24h
series:
  - entity: sensor.total_solar_current_power
    type: line
    name: Current Power
    data_generator: |
      return entity.attributes.forecast.map((entry) => {
        return [new Date(entry.datetime).getTime(), entry.power];
      });
```

## Troubleshooting

### Common Issues

1. **No Forecast Data**
   - Check internet connection
   - Verify latitude/longitude coordinates
   - Check Home Assistant logs for API errors

2. **Inaccurate Forecasts**
   - Review array configurations (declination, azimuth, kWp)
   - Adjust damping factor for system losses
   - Consider local shading or obstructions

3. **Update Failures**
   - API rate limits (integration respects limits)
   - Network connectivity issues
   - Invalid array configurations

### Debug Information

Enable debug logging in `configuration.yaml`:
```yaml
logger:
  default: warning
  logs:
    custom_components.multi_solar_forecast: debug
```

### Performance Considerations

- Update interval is set to 1 hour by default
- API calls are made concurrently for multiple arrays
- Failed updates for individual arrays don't affect others
- Previous data is retained when updates fail

## API Information

This integration uses the Open-Meteo Weather API:
- **Service**: https://api.open-meteo.com
- **Documentation**: https://open-meteo.com/en/docs
- **Rate Limits**: Respected automatically
- **No API Key Required**: Free tier available

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Submit a pull request

### Development Setup

1. Clone the repository
2. Set up a Home Assistant development environment
3. Link the integration to your development instance
4. Test with various array configurations

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Inspired by the original [ha-open-meteo-solar-forecast](https://github.com/rany2/ha-open-meteo-solar-forecast)
- Uses the Open-Meteo weather API
- Built for the Home Assistant community

## Support

- GitHub Issues: Report bugs and request features
- Home Assistant Community: Discussion and support
- Documentation: This README and inline code comments
