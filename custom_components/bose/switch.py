"""Support for Bose power switch."""

from typing import Any

from pybose.BoseResponse import ContentNowPlaying
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
        [BoseTVSwitch(speaker, system_info, config_entry)], update_before_add=True
    )


class BoseTVSwitch(SwitchEntity):
    """Representation of a Bose device as a switch."""

    def __init__(self, speaker: BoseSpeaker, speaker_info, config_entry) -> None:
        """Initialize the switch."""
        self.speaker = speaker
        self._name = "Source TV"
        self._is_on_tv = False
        self.speaker_info = speaker_info
        self.config_entry = config_entry

        self.speaker.attach_receiver(self._parse_message)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the speaker."""
        await self.speaker.switch_tv_source()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the speaker."""
        await self.speaker.set_power_state(False)
        self.async_write_ha_state()

    def _parse_message(self, data):
        """Parse the message from the speaker."""
        if data.get("header", {}).get("resource") == "/content/nowPlaying":
            self._parse_now_playing(ContentNowPlaying(data.get("body")))

    def _parse_now_playing(self, data: ContentNowPlaying):
        self._is_on_tv = (
            data.get("container", {}).get("contentItem", {}).get("source") == "PRODUCT"
            and data.get("container", {}).get("contentItem", {}).get("sourceAccount")
            == "TV"
        )

    async def async_update(self) -> None:
        """Update the switch state."""
        now_playing = await self.speaker.get_now_playing()
        self._parse_now_playing(now_playing)

    @property
    def is_on(self) -> bool:
        """Return if the device is on."""
        return self._is_on_tv

    @property
    def name(self) -> str:
        """Return the name of the switch."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique ID for this entity."""
        return f"{self.config_entry.data['guid']}_tv_source_switch"

    @property
    def device_info(self):
        """Return device information about this entity."""
        return {
            "identifiers": {(DOMAIN, self.config_entry.data["guid"])},
            "name": self.speaker_info["name"],
            "manufacturer": "Bose",
            "model": self.speaker_info["productName"],
            "sw_version": self.speaker_info["softwareVersion"],
        }
