"""Support for Bose battery status sensor."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .bose.battery import (
    BoseBatteryLevelSensor,
    BoseBatteryTimeTillEmpty,
    BoseBatteryTimeTillFull,
)
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bose battery sensor if supported."""
    speaker = hass.data[DOMAIN][config_entry.entry_id]["speaker"]

    battery_status = await speaker.get_battery_status()

    async_add_entities(
        [
            BoseBatteryLevelSensor(speaker, battery_status, config_entry),
            BoseBatteryTimeTillEmpty(speaker, battery_status, config_entry),
            BoseBatteryTimeTillFull(speaker, battery_status, config_entry),
        ],
        update_before_add=False,
    )
