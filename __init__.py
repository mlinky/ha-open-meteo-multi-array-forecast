"""
Multi-Array Solar Forecast Integration for Home Assistant with Energy Dashboard support.

This integration provides solar power forecasting for multiple solar arrays
using the Open-Meteo weather API and integrates with the Home Assistant Energy Dashboard.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import SolarForecastCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

SERVICE_UPDATE_FORECAST = "update_forecast"
SERVICE_GET_HOURLY_FORECAST = "get_hourly_forecast"
SERVICE_GET_ENERGY_DASHBOARD_FORECAST = "get_energy_dashboard_forecast"
SERVICE_GET_TOTAL_SYSTEM_FORECAST = "get_total_system_forecast"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Multi-Array Solar Forecast integration."""
    hass.data.setdefault(DOMAIN, {})
    
    # Register services
    async def handle_update_forecast(call: ServiceCall) -> None:
        """Handle the update forecast service call."""
        entry_id = call.data.get("entry_id")
        if entry_id and entry_id in hass.data[DOMAIN]:
            coordinator = hass.data[DOMAIN][entry_id]
            await coordinator.async_request_refresh()
        else:
            # Update all coordinators if no specific entry_id
            for coordinator in hass.data[DOMAIN].values():
                if isinstance(coordinator, SolarForecastCoordinator):
                    await coordinator.async_request_refresh()

    async def handle_get_hourly_forecast(call: ServiceCall) -> Dict[str, Any]:
        """Handle the get hourly forecast service call."""
        entry_id = call.data.get("entry_id")
        array_name = call.data.get("array_name")
        days = call.data.get("days", 1)
        
        if entry_id and entry_id in hass.data[DOMAIN]:
            coordinator = hass.data[DOMAIN][entry_id]
            if isinstance(coordinator, SolarForecastCoordinator):
                forecast_data = coordinator.get_hourly_forecast(array_name, days)
                return {"forecast": forecast_data}
        
        return {"forecast": []}

    async def handle_get_energy_dashboard_forecast(call: ServiceCall) -> Dict[str, Any]:
        """Handle the get energy dashboard forecast service call."""
        entry_id = call.data.get("entry_id")
        forecast_type = call.data.get("forecast_type", "today")
        
        if entry_id and entry_id in hass.data[DOMAIN]:
            coordinator = hass.data[DOMAIN][entry_id]
            if isinstance(coordinator, SolarForecastCoordinator):
                forecast_data = coordinator.get_energy_dashboard_forecast(forecast_type)
                return {
                    "forecast_data": forecast_data,
                    "forecast_type": forecast_type,
                    "entry_id": entry_id,
                }
        
        return {"forecast_data": {}, "error": "Invalid entry_id or coordinator not found"}

    async def handle_get_total_system_forecast(call: ServiceCall) -> Dict[str, Any]:
        """Handle the get total system forecast service call."""
        entry_id = call.data.get("entry_id")
        hours = call.data.get("hours", 24)
        
        if entry_id and entry_id in hass.data[DOMAIN]:
            coordinator = hass.data[DOMAIN][entry_id]
            if isinstance(coordinator, SolarForecastCoordinator):
                # Get combined forecast for specified hours
                combined_data = coordinator._combine_array_data()
                timestamps = combined_data.get("timestamps", [])
                power_values = combined_data.get("power_forecast", [])
                
                if timestamps and power_values:
                    from datetime import datetime, timedelta
                    from zoneinfo import ZoneInfo
                    
                    now = datetime.now().astimezone()
                    end_time = now + timedelta(hours=hours)
                    uk_tz = ZoneInfo('Europe/London')
                    
                    forecast = []
                    total_energy = 0.0
                    
                    for i, timestamp in enumerate(timestamps):
                        if timestamp.replace(tzinfo=uk_tz) > end_time.replace(tzinfo=uk_tz):
                            break
                        if timestamp.replace(tzinfo=uk_tz) >= now.replace(tzinfo=uk_tz) and i < len(power_values):
                            energy_kwh = power_values[i]
                            total_energy += energy_kwh
                            forecast.append({
                                "datetime": timestamp.isoformat(),
                                "power_kw": round(power_values[i], 3),
                                "energy_kwh": round(energy_kwh, 3),
                            })
                    
                    # Calculate system totals
                    total_kwp = sum(array.get("kwp", 0) for array in coordinator.arrays)
                    
                    return {
                        "forecast": forecast,
                        "total_energy_kwh": round(total_energy, 3),
                        "system_kwp": total_kwp,
                        "arrays_count": len(coordinator.arrays),
                        "hours_requested": hours,
                        "data_points": len(forecast),
                        "generated_at": now.isoformat(),
                    }
        
        return {"forecast": [], "error": "Invalid entry_id or no data available"}

    # Register all services
    hass.services.async_register(
        DOMAIN,
        SERVICE_UPDATE_FORECAST,
        handle_update_forecast,
    )
    
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_HOURLY_FORECAST,
        handle_get_hourly_forecast,
    )
    
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_ENERGY_DASHBOARD_FORECAST,
        handle_get_energy_dashboard_forecast,
    )
    
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_TOTAL_SYSTEM_FORECAST,
        handle_get_total_system_forecast,
    )
    
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Multi-Array Solar Forecast from a config entry."""
    from .const import CONF_ARRAYS
    from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
    
    # Create coordinator
    coordinator = SolarForecastCoordinator(
        hass,
        entry.data[CONF_LATITUDE],
        entry.data[CONF_LONGITUDE],
        entry.data[CONF_ARRAYS],
    )

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Set up entry update listener
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
