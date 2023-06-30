# IPMItool connector for Home Assistant

## What is IPMI?
IPMI (Intelligent Platform Management Interface) is a set of standardized specifications for 
hardware-based platform management systems that makes it possible to control and monitor servers centrally.

## Home Assistant integration
This integration allows you to monitor and control servers that support IPMI.
It does this using the well known [`ipmitool`](https://linux.die.net/man/1/ipmitool). It's not easy
to install this tool in a HASS installation and that's why this integration depends on an addon
that is basically just a webserver that can execute `ipmitool` commands.

You can get the `ipmi-server` addon from [here](https://github.com/ateodorescu/home-assistant-addons).
Don't forget to start the addon before adding servers to the integration.

## Installation
Just copy the `custom_components` folder in your home assistant `config` folder. 
Restart HASS and then add the `ipmitool` integration.

## What does the integration?
The component allows you to configure multiple servers that have unique aliases. 
For each server that you configure the component will add all available `sensors`, 5 `actions` and 1 `switch`.

The following `sensors` will be added:
- all temperature sensors
- all fan sensors
- all voltage sensors
- all power sensors

The following `actions` are added:
- power on
- power off
- power cycle
- power reset
- soft shutdown

The `switch` allows you to turn on the server and shut it down gracefully.

