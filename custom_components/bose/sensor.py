"""Support for Bose battery status sensor."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .bose.battery import (
    BoseBatteryLevelSensor,
    BoseBatteryTimeTillEmpty,
    BoseBatteryTimeTillFull,
)
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Bose battery sensor if supported."""
    speaker = hass.data[DOMAIN][config_entry.entry_id]["speaker"]

    try:
        battery_status = await speaker.get_battery_status()

        async_add_entities(
            [
                BoseBatteryLevelSensor(speaker, battery_status, config_entry),
                BoseBatteryTimeTillEmpty(speaker, battery_status, config_entry),
                BoseBatteryTimeTillFull(speaker, battery_status, config_entry),
            ],
            update_before_add=False,
        )
    except Exception as e:  # noqa: BLE001
        if e.args[1] == 0:
            logging.debug(
                "Speaker does not support battery status for %s",
                config_entry.data["ip"],
            )
        else:
            logging.error(
                "Error setting up Bose battery sensor for %s",
                config_entry.data["ip"],
            )
