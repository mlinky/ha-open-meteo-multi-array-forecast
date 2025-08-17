"""
Sensor platform for Multi-Array Solar Forecast integration with Energy Dashboard support.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Any, Dict, List, Optional

from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
    SensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SENSOR_TYPES, ENERGY_SENSOR_TYPES
from .coordinator import SolarForecastCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up solar forecast sensors from a config entry."""
    coordinator: SolarForecastCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    entities = []
    
    # Create sensors for each array
    for array in coordinator.arrays:
        array_name = array[CONF_NAME]
        
        for sensor_type, sensor_config in SENSOR_TYPES.items():
            entities.append(
                SolarArraySensor(
                    coordinator,
                    config_entry.entry_id,
                    array_name,
                    sensor_type,
                    sensor_config,
                )
            )
    
    # Create total sensors (sum of all arrays)
    for sensor_type, sensor_config in SENSOR_TYPES.items():
        entities.append(
            SolarTotalSensor(
                coordinator,
                config_entry.entry_id,
                sensor_type,
                sensor_config,
            )
        )
    
    # Create Energy Dashboard specific sensors
    for sensor_type, sensor_config in ENERGY_SENSOR_TYPES.items():
        entities.append(
            SolarEnergyDashboardSensor(
                coordinator,
                config_entry.entry_id,
                sensor_type,
                sensor_config,
            )
        )
    
    async_add_entities(entities)


class SolarArraySensor(CoordinatorEntity, SensorEntity):
    """Sensor for individual solar array metrics."""
    
    def __init__(
        self,
        coordinator: SolarForecastCoordinator,
        entry_id: str,
        array_name: str,
        sensor_type: str,
        sensor_config: Dict[str, Any],
    ):
        """Initialize the sensor."""
        super().__init__(coordinator)
        
        self.coordinator = coordinator
        self.entry_id = entry_id
        self.array_name = array_name
        self.sensor_type = sensor_type
        
        # Entity attributes
        self._attr_name = f"{array_name} {sensor_config['name']}"
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_{array_name}_{sensor_type}"
        
        # Sensor configuration
        if sensor_config["unit"] == "kW":
            self._attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
            self._attr_device_class = SensorDeviceClass.POWER
        elif sensor_config["unit"] == "kWh":
            self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
            self._attr_device_class = SensorDeviceClass.ENERGY
        
        if sensor_config["state_class"] == "measurement":
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif sensor_config["state_class"] == "total_increasing":
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
    
    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.entry_id}_{self.array_name}")},
            name=f"Solar Array {self.array_name}",
            manufacturer="Multi-Array Solar Forecast",
            model="Solar Array",
            sw_version="1.0.0",
        )
    
    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        
        array_data = self.coordinator.data.get(self.array_name, {})
        value = array_data.get(self.sensor_type)
        
        if value is not None:
            # Round to 2 decimal places
            return round(float(value), 2)
        
        return None
    
    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and self.array_name in self.coordinator.data
        )
    
    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional state attributes."""
        if not self.coordinator.data or self.array_name not in self.coordinator.data:
            return {}
        
        array_data = self.coordinator.data[self.array_name]
        attributes = {}
        
        # Add array information
        array_info = array_data.get("array_info", {})
        if array_info:
            attributes.update({
                "kwp": array_info.get("kwp"),
                "declination": array_info.get("declination"),
                "azimuth": array_info.get("azimuth"),
                "damping": array_info.get("damping"),
            })
        
        # Add forecast data for power sensors
        if self.sensor_type == "current_power":
            timestamps = array_data.get("timestamps", [])
            power_values = array_data.get("power_forecast", [])
            
            if timestamps and power_values:
                # Provide next 24 hours of forecast
                now = datetime.now().astimezone()
                forecast_24h = []
                uk_tz = ZoneInfo('Europe/London')
                
                for i, timestamp in enumerate(timestamps):
                    if timestamp.replace(tzinfo=uk_tz) >= now.replace(tzinfo=uk_tz) and len(forecast_24h) < 24:
                        if i < len(power_values):
                            forecast_24h.append({
                                "datetime": timestamp.isoformat(),
                                "power": round(power_values[i], 2),
                            })
                
                attributes["forecast"] = forecast_24h
        
        # Add last update time
        last_updated = array_data.get("last_updated")
        if last_updated:
            attributes["last_updated"] = last_updated
            
        return attributes


class SolarTotalSensor(CoordinatorEntity, SensorEntity):
    """Sensor for total across all solar arrays."""
    
    def __init__(
        self,
        coordinator: SolarForecastCoordinator,
        entry_id: str,
        sensor_type: str,
        sensor_config: Dict[str, Any],
    ):
        """Initialize the total sensor."""
        super().__init__(coordinator)
        
        self.coordinator = coordinator
        self.entry_id = entry_id
        self.sensor_type = sensor_type
        
        # Entity attributes
        self._attr_name = f"Total Solar {sensor_config['name']}"
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_total_{sensor_type}"
        
        # Sensor configuration
        if sensor_config["unit"] == "kW":
            self._attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
            self._attr_device_class = SensorDeviceClass.POWER
        elif sensor_config["unit"] == "kWh":
            self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
            self._attr_device_class = SensorDeviceClass.ENERGY
        
        if sensor_config["state_class"] == "measurement":
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif sensor_config["state_class"] == "total_increasing":
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
    
    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.entry_id}_total")},
            name="Total Solar System",
            manufacturer="Multi-Array Solar Forecast",
            model="Solar System",
            sw_version="1.0.0",
        )
    
    @property
    def native_value(self) -> float | None:
        """Return the total value across all arrays."""
        if not self.coordinator.data:
            return None
        
        total = 0.0
        arrays_with_data = 0
        
        for array_data in self.coordinator.data.values():
            value = array_data.get(self.sensor_type)
            if value is not None:
                total += float(value)
                arrays_with_data += 1
        
        # Only return total if we have data from at least one array
        if arrays_with_data > 0:
            return round(total, 2)
        
        return None
    
    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and len(self.coordinator.data) > 0
        )
    
    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional state attributes."""
        if not self.coordinator.data:
            return {}
        
        attributes = {
            "arrays_count": len(self.coordinator.arrays),
            "arrays_with_data": len([
                data for data in self.coordinator.data.values()
                if data.get(self.sensor_type) is not None
            ]),
        }
        
        # Add individual array values for debugging
        array_values = {}
        for array in self.coordinator.arrays:
            array_name = array[CONF_NAME]
            if array_name in self.coordinator.data:
                value = self.coordinator.data[array_name].get(self.sensor_type)
                if value is not None:
                    array_values[array_name] = round(float(value), 2)
        
        if array_values:
            attributes["individual_arrays"] = array_values
        
        # Add combined forecast for power sensors
        if self.sensor_type == "current_power":
            combined_forecast = self._get_combined_forecast()
            if combined_forecast:
                attributes["forecast"] = combined_forecast
        
        # Add system totals
        total_kwp = sum(array.get("kwp", 0) for array in self.coordinator.arrays)
        attributes["total_system_kwp"] = total_kwp
        
        return attributes
    
    def _get_combined_forecast(self) -> list[Dict[str, Any]]:
        """Get combined forecast data from all arrays."""
        if not self.coordinator.data:
            return []
        
        # Get timestamps from first array (should be same for all)
        first_array_data = next(iter(self.coordinator.data.values()), {})
        timestamps = first_array_data.get("timestamps", [])
        
        if not timestamps:
            return []
        
        # Combine power values from all arrays
        combined_forecast = []
        now = datetime.now().astimezone()
        uk_tz = ZoneInfo('Europe/London')
        
        for i, timestamp in enumerate(timestamps):
            if timestamp.replace(tzinfo=uk_tz) >= now.replace(tzinfo=uk_tz) and len(combined_forecast) < 24:
                total_power = 0.0
                arrays_with_data = 0
                
                for array_data in self.coordinator.data.values():
                    power_values = array_data.get("power_forecast", [])
                    if i < len(power_values) and power_values[i] is not None:
                        total_power += power_values[i]
                        arrays_with_data += 1
                
                if arrays_with_data > 0:
                    combined_forecast.append({
                        "datetime": timestamp.isoformat(),
                        "power": round(total_power, 2),
                        "arrays_contributing": arrays_with_data,
                    })
        
        return combined_forecast


class SolarEnergyDashboardSensor(CoordinatorEntity, SensorEntity):
    """Energy Dashboard specific sensor for solar production forecast."""
    
    def __init__(
        self,
        coordinator: SolarForecastCoordinator,
        entry_id: str,
        sensor_type: str,
        sensor_config: Dict[str, Any],
    ):
        """Initialize the energy dashboard sensor."""
        super().__init__(coordinator)
        
        self.coordinator = coordinator
        self.entry_id = entry_id
        self.sensor_type = sensor_type
        
        # Entity attributes
        self._attr_name = sensor_config['name']
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_energy_{sensor_type}"
        
        # Sensor configuration - Energy Dashboard sensors are always energy-based
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
    
    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.entry_id}_energy_dashboard")},
            name="Solar Energy Forecast",
            manufacturer="Multi-Array Solar Forecast",
            model="Energy Dashboard Integration",
            sw_version="1.0.0",
        )
    
    @property
    def native_value(self) -> float | None:
        """Return the forecast energy value."""
        if not self.coordinator.data:
            return None
        
        # Calculate total energy across all arrays
        total_energy = 0.0
        arrays_with_data = 0
        
        for array_data in self.coordinator.data.values():
            energy_value = None
            
            if self.sensor_type == "energy_production_today":
                energy_value = array_data.get("today_energy")
            elif self.sensor_type == "energy_production_tomorrow":
                energy_value = array_data.get("tomorrow_energy")
            elif self.sensor_type == "energy_production_remaining_today":
                energy_value = self._calculate_remaining_today_energy(array_data)
            elif self.sensor_type == "energy_production_this_hour":
                energy_value = self._calculate_this_hour_energy(array_data)
            elif self.sensor_type == "energy_production_next_hour":
                energy_value = self._calculate_next_hour_energy(array_data)
            
            if energy_value is not None:
                total_energy += float(energy_value)
                arrays_with_data += 1
        
        if arrays_with_data > 0:
            return round(total_energy, 3)  # Higher precision for energy values
        
        return None
    
    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and len(self.coordinator.data) > 0
        )
    
    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return energy dashboard specific attributes."""
        if not self.coordinator.data:
            return {}
        
        attributes = {
            "arrays_count": len(self.coordinator.arrays),
            "integration": DOMAIN,
            "unit_of_measurement": self._attr_native_unit_of_measurement,
        }
        
        # Add forecast data that the energy dashboard can use
        if self.sensor_type in ["energy_production_today", "energy_production_tomorrow"]:
            forecast_data = self._get_energy_forecast_data()
            if forecast_data:
                attributes["forecast"] = forecast_data
        
        # Add system configuration info
        total_kwp = sum(array.get("kwp", 0) for array in self.coordinator.arrays)
        attributes["total_system_kwp"] = total_kwp
        
        return attributes
    
    def _calculate_remaining_today_energy(self, array_data: Dict[str, Any]) -> float:
        """Calculate remaining energy production for today."""
        timestamps = array_data.get("timestamps", [])
        power_values = array_data.get("power_forecast", [])
        
        if not timestamps or not power_values:
            return 0.0
        
        now = datetime.now().astimezone()
        today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        uk_tz = ZoneInfo('Europe/London')
        
        remaining_energy = 0.0
        
        for i, timestamp in enumerate(timestamps):
            # Only count future hours today
            if (now.replace(tzinfo=uk_tz) <= timestamp.replace(tzinfo=uk_tz) <= today_end.replace(tzinfo=uk_tz) 
                and i < len(power_values) and power_values[i] is not None):
                remaining_energy += power_values[i]  # Assuming 1-hour intervals
        
        return remaining_energy
    
    def _calculate_this_hour_energy(self, array_data: Dict[str, Any]) -> float:
        """Calculate energy production for the current hour."""
        timestamps = array_data.get("timestamps", [])
        power_values = array_data.get("power_forecast", [])
        
        if not timestamps or not power_values:
            return 0.0
        
        now = datetime.now().astimezone()
        current_hour_start = now.replace(minute=0, second=0, microsecond=0)
        current_hour_end = current_hour_start + timedelta(hours=1)
        uk_tz = ZoneInfo('Europe/London')
        
        for i, timestamp in enumerate(timestamps):
            if (current_hour_start.replace(tzinfo=uk_tz) <= timestamp.replace(tzinfo=uk_tz) < current_hour_end.replace(tzinfo=uk_tz) 
                and i < len(power_values) and power_values[i] is not None):
                return power_values[i]  # Return power as energy for 1-hour period
        
        return 0.0
    
    def _calculate_next_hour_energy(self, array_data: Dict[str, Any]) -> float:
        """Calculate energy production for the next hour."""
        timestamps = array_data.get("timestamps", [])
        power_values = array_data.get("power_forecast", [])
        
        if not timestamps or not power_values:
            return 0.0
        
        now = datetime.now().astimezone()
        next_hour_start = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        next_hour_end = next_hour_start + timedelta(hours=1)
        uk_tz = ZoneInfo('Europe/London')
        
        for i, timestamp in enumerate(timestamps):
            if (next_hour_start.replace(tzinfo=uk_tz) <= timestamp.replace(tzinfo=uk_tz) < next_hour_end.replace(tzinfo=uk_tz) 
                and i < len(power_values) and power_values[i] is not None):
                return power_values[i]  # Return power as energy for 1-hour period
        
        return 0.0
    
    def _get_energy_forecast_data(self) -> List[Dict[str, Any]]:
        """Get detailed energy forecast data for the energy dashboard."""
        if not self.coordinator.data:
            return []
        
        # Get combined forecast from all arrays
        combined_data = self.coordinator._combine_array_data()
        timestamps = combined_data.get("timestamps", [])
        power_values = combined_data.get("power_forecast", [])
        
        if not timestamps or not power_values:
            return []
        
        forecast_data = []
        now = datetime.now().astimezone()
        
        # Determine time range based on sensor type
        if self.sensor_type == "energy_production_today":
            start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = start_time + timedelta(days=1)
        elif self.sensor_type == "energy_production_tomorrow":
            start_time = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            end_time = start_time + timedelta(days=1)
        else:
            start_time = now
            end_time = now + timedelta(hours=48)  # Default to 48 hours
        
        uk_tz = ZoneInfo('Europe/London')
        
        for i, timestamp in enumerate(timestamps):
            if (start_time.replace(tzinfo=uk_tz) <= timestamp.replace(tzinfo=uk_tz) < end_time.replace(tzinfo=uk_tz) 
                and i < len(power_values) and power_values[i] is not None):
                forecast_data.append({
                    "datetime": timestamp.isoformat(),
                    "power": round(power_values[i], 3),
                    "energy": round(power_values[i], 3),  # Assuming 1-hour intervals
                })
        
        return forecast_data
