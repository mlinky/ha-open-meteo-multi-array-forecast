"""
Multi-Array Solar Forecast Integration for Home Assistant.

This integration provides solar power forecasting for multiple solar arrays
using the Open-Meteo weather API.
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
