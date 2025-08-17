"""
Constants for the Multi-Array Solar Forecast integration.
"""

DOMAIN = "multi_solar_forecast"

# Configuration keys
CONF_ARRAYS = "arrays"
CONF_DECLINATION = "declination"
CONF_AZIMUTH = "azimuth"
CONF_KWP = "kwp"
CONF_DAMPING = "damping"
CONF_HORIZON = "horizon"

# Default values
DEFAULT_DECLINATION = 30.0
DEFAULT_AZIMUTH = 180.0
DEFAULT_KWP = 5.0
DEFAULT_DAMPING = 0.0

# API Configuration
API_BASE_URL = "https://api.open-meteo.com/v1/forecast"
API_TIMEOUT = 30
MAX_FORECAST_DAYS = 7

# Sensor types
SENSOR_TYPES = {
    "current_power": {
        "name": "Current Power",
        "unit": "kW",
        "device_class": "power",
        "state_class": "measurement",
    },
    "today_energy": {
        "name": "Today Energy",
        "unit": "kWh",
        "device_class": "energy",
        "state_class": "total_increasing",
    },
    "tomorrow_energy": {
        "name": "Tomorrow Energy",
        "unit": "kWh",
        "device_class": "energy",
        "state_class": "total_increasing",
    },
    "peak_power_today": {
        "name": "Peak Power Today",
        "unit": "kW",
        "device_class": "power",
        "state_class": "measurement",
    },
    "peak_power_today_remaining": {
        "name": "Peak Power Remaining",
        "unit": "kW",
        "device_class": "power",
        "state_class": "measurement",
    },
    "peak_power_tomorrow": {
        "name": "Peak Power Tomorrow",
        "unit": "kW",
        "device_class": "power",
        "state_class": "measurement",
    },
}

# Energy Dashboard specific sensor types (compatible with HA Energy Dashboard)
ENERGY_SENSOR_TYPES = {
    "energy_production_today": {
        "name": "Solar Production Today",
        "unit": "kWh",
        "device_class": "energy",
        "state_class": "total_increasing",
        "icon": "mdi:solar-power",
    },
    "energy_production_tomorrow": {
        "name": "Solar Production Tomorrow",
        "unit": "kWh",
        "device_class": "energy",
        "state_class": "total_increasing",
        "icon": "mdi:solar-power",
    },
    "energy_production_remaining_today": {
        "name": "Solar Production Remaining Today",
        "unit": "kWh",
        "device_class": "energy",
        "state_class": "total_increasing",
        "icon": "mdi:solar-power",
    },
    "energy_production_this_hour": {
        "name": "Solar Production This Hour",
        "unit": "kWh",
        "device_class": "energy",
        "state_class": "total_increasing",
        "icon": "mdi:solar-power",
    },
    "energy_production_next_hour": {
        "name": "Solar Production Next Hour",
        "unit": "kWh",
        "device_class": "energy",
        "state_class": "total_increasing",
        "icon": "mdi:solar-power",
    },
}

# Update intervals
DEFAULT_UPDATE_INTERVAL = 3600  # 1 hour in seconds
FAST_UPDATE_INTERVAL = 1800     # 30 minutes in seconds
SLOW_UPDATE_INTERVAL = 7200     # 2 hours in seconds
