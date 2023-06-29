"""Provides device actions for IPMI server."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_TYPE
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import device_registry as dr
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, TemplateVarsType

from . import PyIpmiData
from .const import (
    DOMAIN,
    INTEGRATION_SUPPORTED_COMMANDS,
    PYIPMI_DATA,
    USER_AVAILABLE_COMMANDS,
)

ACTION_TYPES = {cmd.replace(".", "_") for cmd in INTEGRATION_SUPPORTED_COMMANDS}

ACTION_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(ACTION_TYPES),
    }
)


async def async_get_actions(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device actions for IPMI servers."""
    if (entry_id := _get_entry_id_from_device_id(hass, device_id)) is None:
        return []
    base_action = {
        CONF_DEVICE_ID: device_id,
        CONF_DOMAIN: DOMAIN,
    }
    user_available_commands: set[str] = hass.data[DOMAIN][entry_id][
        USER_AVAILABLE_COMMANDS
    ]
    return [
        {CONF_TYPE: command_name} | base_action
        for command_name in user_available_commands
    ]


async def async_call_action_from_config(
    hass: HomeAssistant,
    config: ConfigType,
    variables: TemplateVarsType,
    context: Context | None,
) -> None:
    """Execute a device action."""
    device_action_name: str = config[CONF_TYPE]
    device_id: str = config[CONF_DEVICE_ID]
    entry_id = _get_entry_id_from_device_id(hass, device_id)
    data: PyIpmiData = hass.data[DOMAIN][entry_id][PYIPMI_DATA]

    command = getattr(data, device_action_name)
    # command()
    await hass.async_add_executor_job(command)


def _get_entry_id_from_device_id(hass: HomeAssistant, device_id: str) -> str | None:
    device_registry = dr.async_get(hass)
    if (device := device_registry.async_get(device_id)) is None:
        return None
    return next(entry for entry in device.config_entries)
