"""Support for Bose power button."""

from asyncio import sleep
import logging
from typing import Any

from pybose.BoseResponse import Preset
from pybose.BoseSpeaker import BoseSpeaker

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers import entity_registry as er

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

    # update presets every 5 minutes
    async def _update_presets():
        while True:
            processed_presets = []
            presets = await _fetch_presets(hass, config_entry)
            for entity in entities:
                entity.update_preset(presets.get(entity.preset_num))
                processed_presets.append(entity.preset_num)

            for presetNum, preset in presets.items():
                if presetNum not in processed_presets:
                    entity = BosePresetbutton(speaker, config_entry, preset, presetNum)
                    entities.append(entity)
                    async_add_entities(
                        [entity],
                        update_before_add=False,
                    )
            await sleep(300)

    hass.loop.create_task(_update_presets())


async def _fetch_presets(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Preset]:
    auth = hass.data[DOMAIN][config_entry.entry_id]["auth"]
    login_result = auth.getControlToken()

    if login_result["access_token"] != config_entry.data["access_token"]:
        logging.debug("Updating access token")
        hass.config_entries.async_update_entry(
            config_entry,
            data={
                **config_entry.data,
                "access_token": login_result["access_token"],
                "refresh_token": login_result["refresh_token"],
                "bose_person_id": login_result["bose_person_id"],
            },
        )

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
        self._name = f"Preset {presetNum}"
        self._preset = preset
        self.preset_num = presetNum
        self.config_entry = config_entry
        self.entity_id = (
            f"{DOMAIN}.{self.config_entry.data['name']}_preset_{self.preset_num}"
        )
        self.update_preset(preset)

    def update_preset(self, preset: Preset) -> None:
        """Update the preset."""
        self._preset = preset
        self._name = (
            preset.get("actions")[0].get("payload").get("contentItem").get("name")
        )
        self.entity_picture = (
            preset.get("actions")[0].get("payload").get("contentItem").get("imageUrl")
        )
        self._attr_entity_picture = (
            preset.get("actions")[0].get("payload").get("contentItem").get("imageUrl")
        )
        if self.hass:
            er.async_get(self.hass).async_update_entity(self.entity_id)
            self.async_write_ha_state()

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
        return f"{self.config_entry.data['guid']}_{self.preset_num}_button"

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information about this entity."""
        return {
            "identifiers": {(DOMAIN, self.config_entry.data["guid"])},
        }
