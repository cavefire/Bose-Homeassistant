"""Support for Bose power button."""

import logging
from typing import Any

from pybose.BoseResponse import Preset
from pybose.BoseSpeaker import BoseSpeaker

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Bose buttons."""
    speaker = hass.data[DOMAIN][config_entry.entry_id]["speaker"]

    presets = await _fetch_presets(hass, config_entry)

    entities = [
        BosePresetbutton(speaker, config_entry, preset, presetNum)
        for presetNum, preset in presets.items()
    ]

    # Add button entity with device info
    async_add_entities(
        entities,
        update_before_add=False,
    )


async def _fetch_presets(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Preset]:
    product_info = await hass.async_add_executor_job(
        hass.data[DOMAIN][config_entry.entry_id]["auth"].fetchProductInformation,
        config_entry.data["guid"],
    )
    return product_info.get("presets", [])


class BosePresetbutton(ButtonEntity):
    """Generic accessory button for Bose speakers."""

    def __init__(
        self,
        speaker: BoseSpeaker,
        config_entry,
        preset: Preset,
        presetNum: int,
    ) -> None:
        """Initialize the button."""
        self._speaker = speaker
        self._name = (
            preset.get("actions")[0].get("payload").get("contentItem").get("name")
        )
        self._attr_entity_picture = (
            preset.get("actions")[0].get("payload").get("contentItem").get("imageUrl")
        )
        self._preset = preset
        self._preset_num = presetNum
        self.config_entry = config_entry

    async def async_press(self, **kwargs) -> None:
        """Press the button."""
        logging.info("Pressing button %s", self._name)
        await self._speaker.request_playback_preset(
            self._preset,
            self.config_entry.data["bose_person_id"],
        )

    async def async_update(self) -> None:
        """Update the button state."""
        logging.info("Updating button %s", self._name)

    @property
    def is_on(self) -> bool:
        """Return if the feature is on."""
        return self._is_on

    @property
    def name(self) -> str:
        """Return the name of the button."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique ID for this entity."""
        return f"{self.config_entry.data['guid']}_{self._preset_num}_button"

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information about this entity."""
        return {
            "identifiers": {(DOMAIN, self.config_entry.data["guid"])},
        }
