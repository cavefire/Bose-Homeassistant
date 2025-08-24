"""Support for Bose power button."""

from pybose.BoseResponse import Preset
from pybose.BoseSpeaker import BoseSpeaker

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import refresh_token
from .const import _LOGGER, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Bose buttons."""
    speaker: BoseSpeaker = hass.data[DOMAIN][config_entry.entry_id]["speaker"]

    presets = (
        (await speaker.get_product_settings()).get("presets", None).get("presets", [])
    )

    entities = [
        BosePresetbutton(speaker, config_entry, preset, presetNum)
        for presetNum, preset in presets.items()
    ]
    entities.append(BoseRefreshTokenButton(speaker, config_entry, hass))

    # Add button entity with device info
    async_add_entities(
        entities,
        update_before_add=False,
    )

    def parse_message(data):
        resource = data.get("header", {}).get("resource")
        body = data.get("body", {})
        if resource == "/system/productSettings":
            presets = body.get("presets", {}).get("presets", {})

            processed_presets = []
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

    speaker.attach_receiver(parse_message)


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
        self._attr_name = f"Preset {presetNum}"
        self._preset = preset
        self.preset_num = presetNum
        self.config_entry = config_entry
        self.entity_id = (
            f"{DOMAIN}.{self.config_entry.data['name']}_preset_{self.preset_num}"
        )
        self.icon = "mdi:folder-play"
        self.update_preset(preset)

    def update_preset(self, preset: Preset) -> None:
        """Update the preset."""
        self._preset = preset
        self._attr_name = (
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
        _LOGGER.info("Pressing button %s", self._attr_name)
        await self._speaker.request_playback_preset(
            self._preset,
            self.config_entry.data["bose_person_id"],
        )

    async def async_update(self) -> None:
        """Update the button state."""
        _LOGGER.info("Updating button %s", self._attr_name)

    @property
    def unique_id(self) -> str:
        """Return a unique ID for this entity."""
        return f"{self.config_entry.data['guid']}_{self.preset_num}_button"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        return {
            "identifiers": {(DOMAIN, self.config_entry.data["guid"])},
        }


class BoseRefreshTokenButton(ButtonEntity):
    """Button to refresh the token."""

    def __init__(
        self, speaker: BoseSpeaker, config_entry: ConfigEntry, hass: HomeAssistant
    ) -> None:
        """Initialize the button."""
        self._speaker = speaker
        self._attr_name = "Refresh Auth (JWT) Token"
        self.entity_id = f"{DOMAIN}.refresh_token_button"
        self.icon = "mdi:refresh"
        self.entity_category = EntityCategory.DIAGNOSTIC
        self._config_entry = config_entry
        self.hass = hass

    async def async_press(self, **kwargs) -> None:
        """Press the button."""
        _LOGGER.info("Refreshing auth token")

        self.hass.async_create_task(
            refresh_token(self.hass, self._config_entry, self._speaker._bose_auth)  # noqa: SLF001
        )

    @property
    def unique_id(self) -> str:
        """Return a unique ID for this entity."""
        return f"{self._config_entry.data['guid']}_jwt_button"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        return {
            "identifiers": {(DOMAIN, self._config_entry.data["guid"])},
        }
