"""Support for Bose power switch."""

from typing import Any

from pybose.BoseResponse import Accessories, SystemInfo, SystemTimeout
from pybose.BoseSpeaker import BoseSpeaker

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import _LOGGER, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Bose switch."""
    speaker: BoseSpeaker = hass.data[DOMAIN][config_entry.entry_id]["speaker"]

    # Fetch system info
    system_info = hass.data[DOMAIN][config_entry.entry_id]["system_info"]
    accessories = hass.data[DOMAIN][config_entry.entry_id]["accessories"]

    entities = []
    if speaker.has_capability("/system/power/timeouts"):
        entities = [BoseStandbySettingSwitch(speaker, system_info, config_entry, hass)]
    else:
        _LOGGER.debug("Speaker does not support system timeouts")

    if accessories:
        if accessories.get("controllable", {}).get("subs", False):
            entities.append(
                BoseSubwooferSwitch(speaker, system_info, accessories, config_entry)
            )
        if accessories.get("controllable", {}).get("rears", False):
            entities.append(
                BoseRearSpeakerSwitch(speaker, system_info, accessories, config_entry)
            )

    # Add switch entity with device info
    async_add_entities(
        entities,
        update_before_add=False,
    )


class BoseAccessorySwitch(SwitchEntity):
    """Generic accessory switch for Bose speakers."""

    def __init__(
        self,
        speaker: BoseSpeaker,
        speaker_info: SystemInfo,
        accessories: Accessories,
        config_entry,
        name: str,
        attribute: str,
    ) -> None:
        """Initialize the switch."""
        self.speaker = speaker
        self._name = name
        self._attribute = attribute
        self._is_on = accessories.get("enabled", {}).get(attribute)
        self.speaker_info = speaker_info
        self.config_entry = config_entry
        self.icon = "mdi:speaker"

        self.speaker.attach_receiver(self._parse_message)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the speaker feature."""
        await self.speaker.put_accessories(**{f"{self._attribute}_enabled": True})
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the speaker feature."""
        await self.speaker.put_accessories(**{f"{self._attribute}_enabled": False})
        self.async_write_ha_state()

    def _parse_message(self, data):
        """Parse the message from the speaker."""
        if data.get("header", {}).get("resource") == "/accessories":
            self._parse_accessories(Accessories(data.get("body")))

    def _parse_accessories(self, data: Accessories):
        """Parse the accessories data."""
        self._is_on = data.get("enabled").get(self._attribute, False)
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Update the switch state."""
        self._parse_accessories(await self.speaker.get_accessories())

    @property
    def is_on(self) -> bool:
        """Return if the feature is on."""
        return self._is_on

    @property
    def name(self) -> str:
        """Return the name of the switch."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique ID for this entity."""
        return f"{self.config_entry.data['guid']}_{self._attribute}_switch"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        return {"identifiers": {(DOMAIN, self.config_entry.data["guid"])}}


class BoseSubwooferSwitch(BoseAccessorySwitch):
    """Switch to turn on/off subwoofers."""

    def __init__(
        self,
        speaker: BoseSpeaker,
        speaker_info: SystemInfo,
        accessories: Accessories,
        config_entry,
    ) -> None:
        """Initialize the switch."""
        super().__init__(
            speaker, speaker_info, accessories, config_entry, "Subwoofers", "subs"
        )


class BoseRearSpeakerSwitch(BoseAccessorySwitch):
    """Switch to turn on/off rear speakers."""

    def __init__(
        self,
        speaker: BoseSpeaker,
        speaker_info: SystemInfo,
        accessories: Accessories,
        config_entry,
    ) -> None:
        """Initialize the switch."""
        super().__init__(
            speaker, speaker_info, accessories, config_entry, "Rear Speakers", "rears"
        )


class BoseStandbySettingSwitch(SwitchEntity):
    """Switch to turn on/off standby setting."""

    def __init__(
        self,
        speaker: BoseSpeaker,
        speaker_info: SystemInfo,
        config_entry,
        hass: HomeAssistant,
    ) -> None:
        """Initialize the switch."""
        self.speaker = speaker
        self._name = "Auto standby"
        self._is_on = None
        self.speaker_info = speaker_info
        self.config_entry = config_entry
        self.icon = "mdi:power-standby"

        self._attr_entity_category = EntityCategory.CONFIG

        self.speaker.attach_receiver(self._parse_message)
        hass.async_create_task(self.async_update())

    def _parse_message(self, data):
        """Parse the message from the speaker."""
        if data.get("header", {}).get("resource") == "/system/power/timeouts":
            result: SystemTimeout = data.get("body")
            self._is_on = result.get("noAudio", False)
            self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the speaker feature."""
        await self.speaker.set_system_timeout(True, False)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the speaker feature."""
        await self.speaker.set_system_timeout(False, False)
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Update the switch state."""
        self._is_on = (await self.speaker.get_system_timeout()).get("noAudio", False)
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        """Return if the feature is on."""
        return self._is_on

    @property
    def name(self) -> str:
        """Return the name of the switch."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique ID for this entity."""
        return f"{self.config_entry.data['guid']}_standby_switch"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        return {"identifiers": {(DOMAIN, self.config_entry.data["guid"])}}
