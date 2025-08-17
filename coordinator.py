"""
Data update coordinator for Multi-Array Solar Forecast integration with Energy Dashboard support.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Any, Dict, List, Optional

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    DOMAIN,
    CONF_ARRAYS,
    CONF_DECLINATION,
    CONF_AZIMUTH,
    CONF_KWP,
    CONF_DAMPING,
    CONF_HORIZON,
    API_BASE_URL,
    API_TIMEOUT,
    MAX_FORECAST_DAYS,
    DEFAULT_UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class SolarForecastCoordinator(DataUpdateCoordinator):
    """Coordinator to fetch solar forecast data for multiple arrays with Energy Dashboard support."""
    
    def __init__(
        self,
        hass: HomeAssistant,
        latitude: float,
        longitude: float,
        arrays: List[Dict[str, Any]],
    ):
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_UPDATE_INTERVAL),
        )
        self.latitude = latitude
        self.longitude = longitude
        self.arrays = arrays
        self.session = async_get_clientsession(hass)
        self._last_successful_update = None

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data from Open-Meteo API for all arrays."""
        try:
            _LOGGER.debug("Fetching solar forecast data for %d arrays", len(self.arrays))
            
            # Fetch data for all arrays concurrently
            tasks = [
                self._fetch_array_forecast(array)
                for array in self.arrays
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            all_forecasts = {}
            successful_updates = 0
            
            for i, result in enumerate(results):
                array_name = self.arrays[i]["name"]
                
                if isinstance(result, Exception):
                    _LOGGER.warning("Failed to fetch data for array %s: %s", array_name, result)
                    # Keep previous data if available
                    if self.data and array_name in self.data:
                        all_forecasts[array_name] = self.data[array_name]
                else:
                    all_forecasts[array_name] = result
                    successful_updates += 1
            
            if successful_updates == 0:
                raise UpdateFailed("Failed to fetch data for any solar arrays")
            
            if successful_updates < len(self.arrays):
                _LOGGER.warning(
                    "Only %d of %d arrays updated successfully",
                    successful_updates,
                    len(self.arrays)
                )
            
            self._last_successful_update = datetime.now()
            return all_forecasts
            
        except Exception as err:
            _LOGGER.error("Error fetching solar forecast data: %s", err)
            raise UpdateFailed(f"Error fetching solar forecast data: {err}") from err

    async def _fetch_array_forecast(self, array: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch forecast data for a specific array."""
        array_name = array["name"]
        _LOGGER.debug("Fetching forecast for array: %s", array_name)
        
        params = {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "hourly": "shortwave_radiation,temperature_2m,cloud_cover,wind_speed_10m",
            "timezone": "auto",
            "forecast_days": MAX_FORECAST_DAYS,
            "models": "gfs_seamless",
        }
        
        _LOGGER.debug("API request parameters for %s: %s", array_name, params)
        
        try:
            _LOGGER.debug("Starting API request for array: %s", array_name)
            timeout = aiohttp.ClientTimeout(total=API_TIMEOUT)
            
            async with self.session.get(API_BASE_URL, params=params, timeout=timeout) as response:
                _LOGGER.debug("Received response for %s - Status: %d", array_name, response.status)
                
                if response.status != 200:
                    _LOGGER.error("API request failed for %s with status %d", array_name, response.status)
                    raise UpdateFailed(f"API request failed with status {response.status}")
                
                _LOGGER.debug("Parsing JSON response for array: %s", array_name)
                data = await response.json()
                
                # Log some basic info about the received data
                if isinstance(data, dict) and 'hourly' in data:
                    hourly_data = data.get('hourly', {})
                    data_points = len(hourly_data.get('time', [])) if hourly_data else 0
                    _LOGGER.debug("Received %d hourly data points for %s", data_points, array_name)
                
                # Process the data for this array
                _LOGGER.debug("Processing forecast data for array: %s", array_name)
                processed_data = self._process_forecast_data(data, array)
                
                _LOGGER.info("Successfully fetched and processed forecast data for array: %s", array_name)
                return processed_data
                
        except asyncio.TimeoutError as err:
            _LOGGER.error("Timeout fetching data for %s after %d seconds", array_name, API_TIMEOUT)
            raise UpdateFailed(f"Timeout fetching data for {array_name}") from err
        except aiohttp.ClientError as err:
            _LOGGER.error("Network error fetching data for %s: %s", array_name, err)
            raise UpdateFailed(f"Network error fetching data for {array_name}: {err}") from err
        except Exception as err:
            _LOGGER.error("Unexpected error processing forecast data for %s: %s", array_name, err, exc_info=True)
            raise UpdateFailed(f"Unexpected error fetching data for {array_name}: {err}") from err

    def _process_forecast_data(self, data: Dict[str, Any], array: Dict[str, Any]) -> Dict[str, Any]:
        """Process raw forecast data into usable format."""
        hourly = data.get("hourly", {})
        times = hourly.get("time", [])
        radiation = hourly.get("shortwave_radiation", [])
        temperature = hourly.get("temperature_2m", [])
        cloud_cover = hourly.get("cloud_cover", [])
        wind_speed = hourly.get("wind_speed_10m", [])
        
        if not times or not radiation:
            _LOGGER.warning("No forecast data received for array %s", array["name"])
            return self._get_empty_forecast_data()
        
        # Extract array parameters
        kwp = array[CONF_KWP]
        declination = array[CONF_DECLINATION]
        azimuth = array[CONF_AZIMUTH]
        damping = array.get(CONF_DAMPING, 0.0)
        
        processed_data = {
            "timestamps": [],
            "power_forecast": [],
            "energy_forecast": [],
            "temperature": [],
            "cloud_cover": [],
            "wind_speed": [],
            "array_info": {
                "kwp": kwp,
                "declination": declination,
                "azimuth": azimuth,
                "damping": damping,
            }
        }
        
        # Process each forecast hour
        for i, time_str in enumerate(times):
            if i >= len(radiation) or radiation[i] is None:
                continue
                
            try:
                timestamp = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                
                # Calculate power output using improved solar model
                power_output = self._calculate_solar_power(
                    radiation[i],
                    kwp,
                    declination,
                    azimuth,
                    damping,
                    timestamp,
                    temperature[i] if i < len(temperature) and temperature[i] is not None else 25.0,
                    cloud_cover[i] if i < len(cloud_cover) and cloud_cover[i] is not None else 0.0
                )
                
                processed_data["timestamps"].append(timestamp)
                processed_data["power_forecast"].append(power_output)
                processed_data["energy_forecast"].append(power_output)  # Will be converted to energy
                
                if i < len(temperature) and temperature[i] is not None:
                    processed_data["temperature"].append(temperature[i])
                else:
                    processed_data["temperature"].append(25.0)
                    
                if i < len(cloud_cover) and cloud_cover[i] is not None:
                    processed_data["cloud_cover"].append(cloud_cover[i])
                else:
                    processed_data["cloud_cover"].append(0.0)
                    
                if i < len(wind_speed) and wind_speed[i] is not None:
                    processed_data["wind_speed"].append(wind_speed[i])
                else:
                    processed_data["wind_speed"].append(0.0)
                    
            except Exception as err:
                _LOGGER.warning("Error processing forecast data point %d: %s", i, err)
                continue
        
        # Calculate summary metrics
        now = datetime.now().astimezone()
        processed_data.update(self._calculate_summary_metrics(processed_data, now))
        
        return processed_data
    
    def _calculate_solar_power(
        self,
        radiation: float,
        kwp: float,
        declination: float,
        azimuth: float,
        damping: float,
        timestamp: datetime,
        temperature: float,
        cloud_cover: float,
    ) -> float:
        """Calculate solar power output using an improved model."""
        if radiation <= 0:
            return 0.0
        
        # Base power calculation
        # Standard test conditions: 1000 W/m² irradiance
        base_power = (radiation / 1000.0) * kwp
        
        # Temperature coefficient (typical -0.4%/°C for silicon panels)
        temp_coefficient = -0.004
        temp_factor = 1 + temp_coefficient * (temperature - 25.0)
        
        # Apply temperature factor
        power_output = base_power * temp_factor
        
        # Apply orientation factor (simplified)
        # This is a very basic model - real calculations would consider sun position
        orientation_factor = self._get_orientation_factor(declination, azimuth, timestamp)
        power_output *= orientation_factor
        
        # Apply cloud cover factor
        cloud_factor = 1.0 - (cloud_cover / 100.0) * 0.8  # 80% reduction at 100% cloud cover
        power_output *= cloud_factor
        
        # Apply system damping/losses
        power_output *= (1 - damping)
        
        # Ensure non-negative power
        return max(0.0, power_output)
    
    def _get_orientation_factor(self, declination: float, azimuth: float, timestamp: datetime) -> float:
        """Calculate a simple orientation factor based on time of day and panel orientation."""
        hour = timestamp.hour
        
        # Simple model based on time of day
        if hour < 6 or hour > 20:
            return 0.0  # No sun
        elif hour < 8 or hour > 18:
            return 0.2  # Low sun
        elif hour < 10 or hour > 16:
            return 0.6  # Medium sun
        else:
            return 1.0  # Peak sun hours
        
        # In a real implementation, you would calculate the actual sun position
        # and panel angle for more accurate results
    
    def _calculate_summary_metrics(self, data: Dict[str, Any], now: datetime) -> Dict[str, Any]:
        """Calculate summary metrics from forecast data."""
        timestamps = data.get("timestamps", [])
        power_values = data.get("power_forecast", [])
        
        if not timestamps or not power_values:
            return self._get_empty_summary_metrics()
        
        # Calculate time boundaries
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow_start = today_start + timedelta(days=1)
        day_after_tomorrow = tomorrow_start + timedelta(days=1)
        
        return {
            "current_power": self._get_current_power(timestamps, power_values, now),
            "today_energy": self._calculate_daily_energy(timestamps, power_values, today_start, tomorrow_start),
            "tomorrow_energy": self._calculate_daily_energy(timestamps, power_values, tomorrow_start, day_after_tomorrow),
            "peak_power_today": self._get_peak_power(timestamps, power_values, today_start, tomorrow_start),
            "peak_power_tomorrow": self._get_peak_power(timestamps, power_values, tomorrow_start, day_after_tomorrow),
            "last_updated": now.isoformat(),
        }
    
    def _get_current_power(self, timestamps: List[datetime], power_values: List[float], now: datetime) -> float:
        """Get current power output estimate."""
        if not timestamps or not power_values:
            return 0.0
            
        # Find the closest timestamp to now
        closest_idx = 0
        min_diff = float('inf')
        uk_tz = ZoneInfo('Europe/London')
        
        for i, timestamp in enumerate(timestamps):
            
            diff = abs((timestamp.replace(tzinfo=uk_tz) - now.replace(tzinfo=uk_tz)).total_seconds())
            if diff < min_diff:
                min_diff = diff
                closest_idx = i
        
        return power_values[closest_idx] if closest_idx < len(power_values) else 0.0
    
    def _calculate_daily_energy(
        self,
        timestamps: List[datetime],
        power_values: List[float],
        start_time: datetime,
        end_time: datetime,
    ) -> float:
        """Calculate total energy for a day (assuming hourly data points)."""
        total_energy = 0.0
        uk_tz = ZoneInfo('Europe/London')
        
        for i, timestamp in enumerate(timestamps):
            if start_time.replace(tzinfo=uk_tz) <= timestamp.replace(tzinfo=uk_tz) < end_time.replace(tzinfo=uk_tz) and i < len(power_values):
                # Assume 1-hour intervals for energy calculation
                total_energy += power_values[i]
        
        return total_energy
    
    def _get_peak_power(
        self,
        timestamps: List[datetime],
        power_values: List[float],
        start_time: datetime,
        end_time: datetime,
    ) -> float:
        """Get peak power for a time period."""
        peak_power = 0.0
        uk_tz = ZoneInfo('Europe/London')
        
        for i, timestamp in enumerate(timestamps):
            if start_time.replace(tzinfo=uk_tz) <= timestamp.replace(tzinfo=uk_tz) < end_time.replace(tzinfo=uk_tz) and i < len(power_values):
                peak_power = max(peak_power, power_values[i])
        
        return peak_power
    
    def _get_empty_forecast_data(self) -> Dict[str, Any]:
        """Return empty forecast data structure."""
        return {
            "timestamps": [],
            "power_forecast": [],
            "energy_forecast": [],
            "temperature": [],
            "cloud_cover": [],
            "wind_speed": [],
            "array_info": {},
            **self._get_empty_summary_metrics(),
        }
    
    def _get_empty_summary_metrics(self) -> Dict[str, Any]:
        """Return empty summary metrics."""
        return {
            "current_power": 0.0,
            "today_energy": 0.0,
            "tomorrow_energy": 0.0,
            "peak_power_today": 0.0,
            "peak_power_tomorrow": 0.0,
            "last_updated": datetime.now().isoformat(),
        }

    def get_hourly_forecast(self, array_name: Optional[str] = None, days: int = 1) -> List[Dict[str, Any]]:
        """Get hourly forecast data for service calls."""
        if not self.data:
            return []
        
        if array_name:
            # Return data for specific array
            if array_name not in self.data:
                return []
            array_data = self.data[array_name]
        else:
            # Return combined data for all arrays
            array_data = self._combine_array_data()
        
        # Format data for service response
        timestamps = array_data.get("timestamps", [])
        power_values = array_data.get("power_forecast", [])
        
        forecast = []
        now = datetime.now().astimezone()
        end_time = now + timedelta(days=days)
        uk_tz = ZoneInfo('Europe/London')
        
        for i, timestamp in enumerate(timestamps):
            if timestamp.replace(tzinfo=uk_tz) > end_time.replace(tzinfo=uk_tz):
                break
            if i < len(power_values):
                forecast.append({
                    "datetime": timestamp.isoformat(),
                    "power": power_values[i],
                })
        
        return forecast
    
    def _combine_array_data(self) -> Dict[str, Any]:
        """Combine data from all arrays."""
        if not self.data:
            return self._get_empty_forecast_data()
        
        # Get first array as template
        first_array = next(iter(self.data.values()))
        combined_data = {
            "timestamps": first_array.get("timestamps", []),
            "power_forecast": [0.0] * len(first_array.get("timestamps", [])),
            "energy_forecast": [0.0] * len(first_array.get("timestamps", [])),
        }
        
        # Sum power values from all arrays
        for array_data in self.data.values():
            power_values = array_data.get("power_forecast", [])
            for i, power in enumerate(power_values):
                if i < len(combined_data["power_forecast"]):
                    combined_data["power_forecast"][i] += power
                    combined_data["energy_forecast"][i] += power
        
        return combined_data
    
    def get_energy_dashboard_forecast(self, forecast_type: str = "today") -> Dict[str, Any]:
        """Get forecast data specifically formatted for the Energy Dashboard."""
        if not self.data:
            return {}
        
        combined_data = self._combine_array_data()
        timestamps = combined_data.get("timestamps", [])
        power_values = combined_data.get("power_forecast", [])
        
        if not timestamps or not power_values:
            return {}
        
        now = datetime.now().astimezone()
        uk_tz = ZoneInfo('Europe/London')
        
        # Determine time range
        if forecast_type == "today":
            start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = start_time + timedelta(days=1)
        elif forecast_type == "tomorrow":
            start_time = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            end_time = start_time + timedelta(days=1)
        else:  # "remaining_today"
            start_time = now
            end_time = now.replace(hour=23, minute=59, second=59) + timedelta(seconds=1)
        
        forecast_data = []
        total_energy = 0.0
        
        for i, timestamp in enumerate(timestamps):
            if (start_time.replace(tzinfo=uk_tz) <= timestamp.replace(tzinfo=uk_tz) < end_time.replace(tzinfo=uk_tz) 
                and i < len(power_values)):
                energy_kwh = power_values[i]  # Assuming 1-hour intervals
                total_energy += energy_kwh
                
                forecast_data.append({
                    "start": timestamp.isoformat(),
                    "end": (timestamp + timedelta(hours=1)).isoformat(),
                    "energy_kwh": round(energy_kwh, 3),
                })
        
        return {
            "forecast": forecast_data,
            "total_energy": round(total_energy, 3),
            "forecast_type": forecast_type,
            "generated_at": now.isoformat(),
        }
