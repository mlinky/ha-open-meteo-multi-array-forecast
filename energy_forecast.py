"""
Energy Dashboard Forecast Extension for ha-open-meteo-multi-array-forecast

This extends the existing integration to provide forecast data compatible with
Home Assistant's Energy Dashboard forecast feature.

Key requirements for Energy Dashboard compatibility:
1. Entity must have device_class ENERGY or POWER with appropriate state_class
2. Must provide forecast data via the forecast attribute
3. Forecast data format must match Home Assistant's expectations
4. Entity should be selectable in the Energy Dashboard configuration
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import MultiSolarForecastCoordinator

_LOGGER = logging.getLogger(__name__)


class EnergyDashboardForecastSensor(CoordinatorEntity, SensorEntity):
    """Sensor for Energy Dashboard compatibility with forecast data."""

    def __init__(
        self,
        coordinator: MultiSolarForecastCoordinator,
        array_name: str | None = None,
    ) -> None:
        """Initialize the forecast sensor."""
        super().__init__(coordinator)
        self._array_name = array_name
        
        # Set entity properties for Energy Dashboard compatibility
        if array_name:
            self._attr_name = f"{array_name} Solar Production Forecast"
            self._attr_unique_id = f"{coordinator.entry_id}_{array_name}_production_forecast"
        else:
            self._attr_name = "Total Solar Production Forecast"
            self._attr_unique_id = f"{coordinator.entry_id}_total_production_forecast"
        
        # Essential for Energy Dashboard recognition
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
        
        # Device info for grouping
        self._attr_device_info = {
            "identifiers": {("multi_solar_forecast", coordinator.entry_id)},
            "name": "Multi-Array Solar Forecast",
            "manufacturer": "Open-Meteo Multi-Array Forecast",
            "model": "Solar Production Forecaster",
        }

    @property
    def native_value(self) -> float | None:
        """Return the current power production."""
        if not self.coordinator.data:
            return None
            
        if self._array_name:
            # Return current power for specific array
            array_data = self.coordinator.data.get("arrays", {}).get(self._array_name)
            if array_data:
                return array_data.get("current_power", 0)
        else:
            # Return total current power
            return self.coordinator.data.get("totals", {}).get("current_power", 0)
        
        return None

    @property
    def forecast(self) -> list[dict[str, Any]] | None:
        """Return forecast data for Energy Dashboard."""
        if not self.coordinator.data:
            return None
            
        forecast_data = []
        
        if self._array_name:
            # Get forecast for specific array
            array_data = self.coordinator.data.get("arrays", {}).get(self._array_name)
            if array_data and "hourly_forecast" in array_data:
                forecast_data = array_data["hourly_forecast"]
        else:
            # Get total forecast
            totals_data = self.coordinator.data.get("totals", {})
            if "hourly_forecast" in totals_data:
                forecast_data = totals_data["hourly_forecast"]
        
        if not forecast_data:
            return None
            
        # Convert to Energy Dashboard format
        energy_forecast = []
        for entry in forecast_data:
            # Energy Dashboard expects datetime and value
            energy_forecast.append({
                "datetime": entry.get("datetime"),
                "value": entry.get("power", 0),  # kW power value
            })
        
        return energy_forecast

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attrs = {}
        
        if self.coordinator.data:
            if self._array_name:
                array_data = self.coordinator.data.get("arrays", {}).get(self._array_name, {})
                attrs.update({
                    "array_name": self._array_name,
                    "kWp": array_data.get("kWp"),
                    "declination": array_data.get("declination"),
                    "azimuth": array_data.get("azimuth"),
                    "today_energy": array_data.get("today_energy"),
                    "tomorrow_energy": array_data.get("tomorrow_energy"),
                })
            else:
                totals_data = self.coordinator.data.get("totals", {})
                attrs.update({
                    "total_kWp": totals_data.get("total_kWp"),
                    "active_arrays": totals_data.get("active_arrays"),
                    "today_energy": totals_data.get("today_energy"),
                    "tomorrow_energy": totals_data.get("tomorrow_energy"),
                })
                
            attrs["last_updated"] = self.coordinator.data.get("last_updated")
            
        return attrs


class EnergyDashboardEnergySensor(CoordinatorEntity, SensorEntity):
    """Energy sensor for daily/total energy tracking in Energy Dashboard."""

    def __init__(
        self,
        coordinator: MultiSolarForecastCoordinator,
        sensor_type: str = "today",
        array_name: str | None = None,
    ) -> None:
        """Initialize the energy sensor."""
        super().__init__(coordinator)
        self._array_name = array_name
        self._sensor_type = sensor_type
        
        # Set entity properties for Energy Dashboard compatibility
        if array_name:
            self._attr_name = f"{array_name} Solar Energy {sensor_type.title()}"
            self._attr_unique_id = f"{coordinator.entry_id}_{array_name}_energy_{sensor_type}"
        else:
            self._attr_name = f"Total Solar Energy {sensor_type.title()}"
            self._attr_unique_id = f"{coordinator.entry_id}_total_energy_{sensor_type}"
        
        # Energy sensor configuration
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        
        # Device info for grouping
        self._attr_device_info = {
            "identifiers": {("multi_solar_forecast", coordinator.entry_id)},
            "name": "Multi-Array Solar Forecast",
            "manufacturer": "Open-Meteo Multi-Array Forecast",
            "model": "Solar Energy Monitor",
        }

    @property
    def native_value(self) -> float | None:
        """Return the energy value."""
        if not self.coordinator.data:
            return None
            
        if self._array_name:
            array_data = self.coordinator.data.get("arrays", {}).get(self._array_name)
            if array_data:
                return array_data.get(f"{self._sensor_type}_energy", 0)
        else:
            totals_data = self.coordinator.data.get("totals", {})
            return totals_data.get(f"{self._sensor_type}_energy", 0)
        
        return None


async def async_setup_energy_dashboard_sensors(
    hass: HomeAssistant,
    coordinator: MultiSolarForecastCoordinator,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up energy dashboard compatible sensors."""
    
    entities = []
    
    # Add total system forecast sensor (main sensor for Energy Dashboard)
    entities.append(EnergyDashboardForecastSensor(coordinator))
    
    # Add total energy sensors
    entities.append(EnergyDashboardEnergySensor(coordinator, "today"))
    entities.append(EnergyDashboardEnergySensor(coordinator, "tomorrow"))
    
    # Add individual array sensors if configured
    if coordinator.data and "arrays" in coordinator.data:
        for array_name in coordinator.data["arrays"].keys():
            # Forecast sensor for each array
            entities.append(EnergyDashboardForecastSensor(coordinator, array_name))
            
            # Energy sensors for each array
            entities.append(EnergyDashboardEnergySensor(coordinator, "today", array_name))
            entities.append(EnergyDashboardEnergySensor(coordinator, "tomorrow", array_name))
    
    async_add_entities(entities)
    
    _LOGGER.info(
        "Added %d energy dashboard compatible sensors for %s",
        len(entities),
        coordinator.entry_id,
    )
