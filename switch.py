"""Support for Bose power switch."""

from typing import Any

from pybose.BoseSpeaker import BoseSpeaker

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bose switch."""
    speaker = hass.data[DOMAIN][config_entry.entry_id]["speaker"]

    # Fetch system info
    system_info = await speaker.get_system_info()

    # Add switch entity with device info
    async_add_entities(
        [BosePowerSwitch(speaker, system_info, config_entry)], update_before_add=True
    )


class BosePowerSwitch(SwitchEntity):
    """Representation of a Bose device as a switch."""

    def __init__(self, speaker: BoseSpeaker, speaker_info, config_entry) -> None:
        """Initialize the switch."""
        self.speaker = speaker
        self._name = f"{speaker_info.name} Power"
        self._device_id = config_entry.data["guid"]
        self._is_on = False  # Default to off

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the speaker."""
        await self.speaker.set_power_state(True)
        self._is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the speaker."""
        await self.speaker.set_power_state(False)
        self._is_on = False
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        """Return if the device is on."""
        return self._is_on

    @property
    def name(self) -> str:
        """Return the name of the switch."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique ID for this entity."""
        return f"{self._device_id}-power"

    @property
    def device_info(self):
        """Return device information for Home Assistant integration."""
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "manufacturer": "Bose",
            "name": self._name,
        }
