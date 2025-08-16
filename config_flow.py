"""
Configuration flow for Multi-Array Solar Forecast integration.
"""
import voluptuous as vol
from typing import Any, Dict, Optional

from homeassistant import config_entries
from homeassistant.const import CONF_NAME, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    CONF_ARRAYS,
    CONF_DECLINATION,
    CONF_AZIMUTH,
    CONF_KWP,
    CONF_DAMPING,
    CONF_HORIZON,
)


class MultiSolarForecastConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Multi-Array Solar Forecast."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self.data = {}
        self.arrays = []
        self.current_array = {}

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # Validate location data
            try:
                self.data.update({
                    CONF_LATITUDE: user_input[CONF_LATITUDE],
                    CONF_LONGITUDE: user_input[CONF_LONGITUDE],
                })
                return await self.async_step_add_array()
            except ValueError:
                errors["base"] = "invalid_location"

        data_schema = vol.Schema({
            vol.Required(CONF_LATITUDE, default=self.hass.config.latitude): cv.latitude,
            vol.Required(CONF_LONGITUDE, default=self.hass.config.longitude): cv.longitude,
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_add_array(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle adding a solar array."""
        errors = {}

        if user_input is not None:
            if user_input.get("add_array"):
                # User wants to add an array
                return await self.async_step_array_config()
            elif user_input.get("finish_setup"):
                # User is done adding arrays
                if not self.arrays:
                    errors["base"] = "no_arrays"
                else:
                    return self._create_entry()

        data_schema = vol.Schema({
            vol.Optional("add_array", default=True): bool,
            vol.Optional("finish_setup", default=False): bool,
        })

        description_placeholders = {
            "arrays_count": len(self.arrays),
            "arrays_list": ", ".join([array[CONF_NAME] for array in self.arrays]) if self.arrays else "None"
        }

        return self.async_show_form(
            step_id="add_array",
            data_schema=data_schema,
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def async_step_array_config(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle configuring a specific solar array."""
        errors = {}

        if user_input is not None:
            # Validate array configuration
            try:
                array_config = {
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_DECLINATION: user_input[CONF_DECLINATION],
                    CONF_AZIMUTH: user_input[CONF_AZIMUTH],
                    CONF_KWP: user_input[CONF_KWP],
                    CONF_DAMPING: user_input.get(CONF_DAMPING, 0.0),
                    CONF_HORIZON: user_input.get(CONF_HORIZON, ""),
                }
                
                # Check for duplicate names
                if any(array[CONF_NAME] == array_config[CONF_NAME] for array in self.arrays):
                    errors[CONF_NAME] = "duplicate_name"
                else:
                    self.arrays.append(array_config)
                    return await self.async_step_add_array()
                    
            except ValueError:
                errors["base"] = "invalid_array_config"

        data_schema = vol.Schema({
            vol.Required(CONF_NAME): str,
            vol.Required(CONF_DECLINATION, default=30): vol.All(vol.Coerce(float), vol.Range(min=0, max=90)),
            vol.Required(CONF_AZIMUTH, default=180): vol.All(vol.Coerce(float), vol.Range(min=0, max=360)),
            vol.Required(CONF_KWP, default=5.0): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=1000)),
            vol.Optional(CONF_DAMPING, default=0.0): vol.All(vol.Coerce(float), vol.Range(min=0, max=1)),
            vol.Optional(CONF_HORIZON, default=""): str,
        })

        return self.async_show_form(
            step_id="array_config",
            data_schema=data_schema,
            errors=errors,
        )

    def _create_entry(self) -> FlowResult:
        """Create the config entry."""
        self.data[CONF_ARRAYS] = self.arrays
        
        title = f"Solar Forecast ({len(self.arrays)} arrays)"
        
        return self.async_create_entry(
            title=title,
            data=self.data,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return MultiSolarForecastOptionsFlow(config_entry)


class MultiSolarForecastOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Multi-Array Solar Forecast."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry
        self.arrays = list(config_entry.data.get(CONF_ARRAYS, []))
        self.current_array_index = None

    async def async_step_init(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle options flow initialization."""
        return await self.async_step_main_menu()

    async def async_step_main_menu(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Show the main options menu."""
        if user_input is not None:
            if user_input.get("action") == "add_array":
                return await self.async_step_add_array()
            elif user_input.get("action") == "edit_array":
                return await self.async_step_select_array_to_edit()
            elif user_input.get("action") == "delete_array":
                return await self.async_step_select_array_to_delete()
            elif user_input.get("action") == "save":
                return self._update_config_entry()

        data_schema = vol.Schema({
            vol.Required("action"): vol.In({
                "add_array": "Add new array",
                "edit_array": "Edit existing array",
                "delete_array": "Delete array",
                "save": "Save changes",
            }),
        })

        description_placeholders = {
            "arrays_count": len(self.arrays),
            "arrays_list": ", ".join([array[CONF_NAME] for array in self.arrays]) if self.arrays else "None"
        }

        return self.async_show_form(
            step_id="main_menu",
            data_schema=data_schema,
            description_placeholders=description_placeholders,
        )

    async def async_step_add_array(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Add a new array."""
        errors = {}

        if user_input is not None:
            try:
                array_config = {
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_DECLINATION: user_input[CONF_DECLINATION],
                    CONF_AZIMUTH: user_input[CONF_AZIMUTH],
                    CONF_KWP: user_input[CONF_KWP],
                    CONF_DAMPING: user_input.get(CONF_DAMPING, 0.0),
                    CONF_HORIZON: user_input.get(CONF_HORIZON, ""),
                }
                
                # Check for duplicate names
                if any(array[CONF_NAME] == array_config[CONF_NAME] for array in self.arrays):
                    errors[CONF_NAME] = "duplicate_name"
                else:
                    self.arrays.append(array_config)
                    return await self.async_step_main_menu()
                    
            except ValueError:
                errors["base"] = "invalid_array_config"

        data_schema = vol.Schema({
            vol.Required(CONF_NAME): str,
            vol.Required(CONF_DECLINATION, default=30): vol.All(vol.Coerce(float), vol.Range(min=0, max=90)),
            vol.Required(CONF_AZIMUTH, default=180): vol.All(vol.Coerce(float), vol.Range(min=0, max=360)),
            vol.Required(CONF_KWP, default=5.0): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=1000)),
            vol.Optional(CONF_DAMPING, default=0.0): vol.All(vol.Coerce(float), vol.Range(min=0, max=1)),
            vol.Optional(CONF_HORIZON, default=""): str,
        })

        return self.async_show_form(
            step_id="add_array",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_select_array_to_edit(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Select an array to edit."""
        if user_input is not None:
            self.current_array_index = int(user_input["array_index"])
            return await self.async_step_edit_array()

        if not self.arrays:
            return await self.async_step_main_menu()

        array_options = {
            str(i): f"{array[CONF_NAME]} ({array[CONF_KWP]}kWp)"
            for i, array in enumerate(self.arrays)
        }

        data_schema = vol.Schema({
            vol.Required("array_index"): vol.In(array_options),
        })

        return self.async_show_form(
            step_id="select_array_to_edit",
            data_schema=data_schema,
        )

    async def async_step_edit_array(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Edit the selected array."""
        if self.current_array_index is None:
            return await self.async_step_main_menu()

        array = self.arrays[self.current_array_index]
        errors = {}

        if user_input is not None:
            try:
                # Check for duplicate names (excluding current array)
                new_name = user_input[CONF_NAME]
                if any(
                    i != self.current_array_index and existing_array[CONF_NAME] == new_name
                    for i, existing_array in enumerate(self.arrays)
                ):
                    errors[CONF_NAME] = "duplicate_name"
                else:
                    # Update the array
                    self.arrays[self.current_array_index] = {
                        CONF_NAME: user_input[CONF_NAME],
                        CONF_DECLINATION: user_input[CONF_DECLINATION],
                        CONF_AZIMUTH: user_input[CONF_AZIMUTH],
                        CONF_KWP: user_input[CONF_KWP],
                        CONF_DAMPING: user_input.get(CONF_DAMPING, 0.0),
                        CONF_HORIZON: user_input.get(CONF_HORIZON, ""),
                    }
                    return await self.async_step_main_menu()
            except ValueError:
                errors["base"] = "invalid_array_config"

        data_schema = vol.Schema({
            vol.Required(CONF_NAME, default=array[CONF_NAME]): str,
            vol.Required(CONF_DECLINATION, default=array[CONF_DECLINATION]): vol.All(vol.Coerce(float), vol.Range(min=0, max=90)),
            vol.Required(CONF_AZIMUTH, default=array[CONF_AZIMUTH]): vol.All(vol.Coerce(float), vol.Range(min=0, max=360)),
            vol.Required(CONF_KWP, default=array[CONF_KWP]): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=1000)),
            vol.Optional(CONF_DAMPING, default=array.get(CONF_DAMPING, 0.0)): vol.All(vol.Coerce(float), vol.Range(min=0, max=1)),
            vol.Optional(CONF_HORIZON, default=array.get(CONF_HORIZON, "")): str,
        })

        return self.async_show_form(
            step_id="edit_array",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_select_array_to_delete(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Select an array to delete."""
        if user_input is not None:
            array_index = int(user_input["array_index"])
            self.arrays.pop(array_index)
            return await self.async_step_main_menu()

        if not self.arrays:
            return await self.async_step_main_menu()

        array_options = {
            str(i): f"{array[CONF_NAME]} ({array[CONF_KWP]}kWp)"
            for i, array in enumerate(self.arrays)
        }

        data_schema = vol.Schema({
            vol.Required("array_index"): vol.In(array_options),
        })

        return self.async_show_form(
            step_id="select_array_to_delete",
            data_schema=data_schema,
        )

    def _update_config_entry(self) -> FlowResult:
        """Update the config entry with new data."""
        new_data = dict(self.config_entry.data)
        new_data[CONF_ARRAYS] = self.arrays
        
        self.hass.config_entries.async_update_entry(
            self.config_entry, data=new_data
        )
        
        return self.async_create_entry(title="", data={})
