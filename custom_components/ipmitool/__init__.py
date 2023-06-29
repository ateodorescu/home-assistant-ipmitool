"""
The "ipmitool" custom component.

This component implements the bare minimum that a component should implement.

Configuration:

To use the ipmi component you will need to add the following to your
configuration.yaml file.

ipmitool:
"""
from __future__ import annotations

import async_timeout
import requests
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import cast

from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

# The domain of your component. Should be equal to the name of your component.
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ALIAS,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_RESOURCES,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    COORDINATOR,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PLATFORMS,
    PYIPMI_DATA,
    PYIPMI_UNIQUE_ID,
    USER_AVAILABLE_COMMANDS,
    INTEGRATION_SUPPORTED_COMMANDS,
    IPMI_URL
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up IPMI from a config entry."""

    # strip out the stale options CONF_RESOURCES,
    # maintain the entry in data in case of version rollback
    if CONF_RESOURCES in entry.options:
        new_data = {**entry.data, CONF_RESOURCES: entry.options[CONF_RESOURCES]}
        new_options = {k: v for k, v in entry.options.items() if k != CONF_RESOURCES}
        hass.config_entries.async_update_entry(
            entry, data=new_data, options=new_options
        )

    config = entry.data
    host = config[CONF_HOST]
    port = config[CONF_PORT]

    alias = config.get(CONF_ALIAS)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    data = PyIpmiData(host, port, alias, username, password)

    async def async_update_data() -> IpmiDeviceInfo:
        """Fetch data from IPMI."""
        async with async_timeout.timeout(10):
            await hass.async_add_executor_job(data.update)
            if not data.device_info:
                raise UpdateFailed("Error fetching IPMI state")
            return data.device_info

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="IPMI resource status",
        update_method=async_update_data,
        update_interval=timedelta(seconds=scan_interval),
    )

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_config_entry_first_refresh()
    deviceInfo = coordinator.data
    # _LOGGER.info(repr(deviceInfo))
    # _LOGGER.info(repr(deviceInfo.sensors))

    _LOGGER.debug("IPMI Sensors Available: %s", deviceInfo)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    unique_id = alias + _unique_id_from_status(deviceInfo)
    if unique_id is None:
        unique_id = entry.entry_id

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        COORDINATOR: coordinator,
        PYIPMI_DATA: data,
        PYIPMI_UNIQUE_ID: unique_id,
        USER_AVAILABLE_COMMANDS: INTEGRATION_SUPPORTED_COMMANDS,
    }

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, unique_id)},
        name=data.name.title(),
        manufacturer=data._device_info.device["manufacturer_name"],
        model=data._device_info.device["product_name"],
        sw_version=data._device_info.device["firmware_revision"],
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)

def _unique_id_from_status(device_info: IpmiDeviceInfo) -> str | None:
    """Find the best unique id value from the status."""
    alias = device_info.alias
    # We must have an alias for this to be unique
    if not alias:
        return None

    manufacturer = device_info.device["manufacturer_name"]
    product_name = device_info.device["product_name"]

    unique_id_group = []
    if manufacturer:
        unique_id_group.append(manufacturer)
    elif product_name:
        unique_id_group.append(product_name)
    if alias:
        unique_id_group.append(alias)
    return "_".join(unique_id_group)

@dataclass
class IpmiDeviceInfo:
    """Device information for the IPMI server."""

    device: dict[str, str] = None
    power_on: bool | False = False
    sensors: dict[str, str] = None
    states: dict[str, str] = None
    alias: str = None

class PyIpmiData:
    """Stores the data retrieved from IPMI.

    For each entity to use, acts as the single point responsible for fetching
    updates from the server.
    """

    def __init__(
        self,
        host: str,
        port: int,
        alias: str | None,
        username: str | None,
        password: str | None,
    ) -> None:
        """Initialize the data object."""

        self._host = host
        self._port = port
        self._alias = alias
        self._username = username
        self._password = password

        self._device_info: IpmiDeviceInfo | None = None

    @property
    def name(self) -> str:
        """Return the name of the IPMI server."""
        return self._alias or f"IPMI-{self._host}"

    @property
    def device_info(self) -> IpmiDeviceInfo:
        """Return the device info for the IPMI server."""
        return self._device_info

    def getJson(self, path: str | None):
            params = {
                "host": self._host,
                "port": self._port,
                "user": self._username,
                "password": self._password
            }
            url = IPMI_URL

            if path is not None:
                url += "/" + path

            ipmi = requests.get(url, params=params)
            return ipmi.json()

    def update(self) -> None:
        try:
            json = self.getJson(None)

            if (json["success"]):
                info = IpmiDeviceInfo()
                info.device = json["device"]
                info.power_on = json["power_on"]
                info.sensors = json["sensors"]
                info.states = json["states"]
                info.alias = self._alias
                self._device_info = info
            else:
                _LOGGER.error(json["message"])
            
        except (Exception) as err: # pylint: disable=broad-except
            _LOGGER.error("Error connecting to IPMI server %s: %s", self._host, err)

    def power_on(self) -> None:
        try:
            self.getJson("power_on")
        except (Exception) as err: # pylint: disable=broad-except
            _LOGGER.error("Error connecting to IPMI server %s: %s", self._host, err)

    def power_off(self) -> None:
        try:
            self.getJson("power_off")
        except (Exception) as err: # pylint: disable=broad-except
            _LOGGER.error("Error connecting to IPMI server %s: %s", self._host, err)

    def power_cycle(self) -> None:
        try:
            self.getJson("power_cycle")
        except (Exception) as err: # pylint: disable=broad-except
            _LOGGER.error("Error connecting to IPMI server %s: %s", self._host, err)

    def power_reset(self) -> None:
        try:
            self.getJson("power_reset")
        except (Exception) as err: # pylint: disable=broad-except
            _LOGGER.error("Error connecting to IPMI server %s: %s", self._host, err)

    def soft_shutdown(self) -> None:
        try:
            self.getJson("soft_shutdown")
        except (Exception) as err: # pylint: disable=broad-except
            _LOGGER.error("Error connecting to IPMI server %s: %s", self._host, err)

