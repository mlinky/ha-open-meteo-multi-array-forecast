"""
Sensor platform for Multi-Array Solar Forecast integration.
"""
from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any, Dict, Optional

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

from .const import DOMAIN, SENSOR_TYPES
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
