"""Support for Bose power button."""

from pybose.BoseResponse import Preset
from pybose.BoseSpeaker import BoseSpeaker

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import _LOGGER, DOMAIN
from .entity import BoseBaseEntity


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

    entities: list[BoseBaseEntity] = [
        BosePresetbutton(speaker, config_entry, preset, presetNum)
        for presetNum, preset in presets.items()
    ]

    # Add Bluetooth pairing button if Bluetooth is supported
    if speaker.has_capability("/bluetooth/sink/pairable"):
        entities.append(BoseBluetoothPairButton(speaker, config_entry))

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
                # Only BosePresetbutton instances implement update_preset
                if isinstance(entity, BosePresetbutton):
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


class BosePresetbutton(BoseBaseEntity, ButtonEntity):
    """Generic accessory button for Bose speakers."""

    def __init__(
        self,
        speaker: BoseSpeaker,
        config_entry,
        preset: Preset,
        presetNum: str,
    ) -> None:
        """Initialize the button."""

        BoseBaseEntity.__init__(self, speaker)
        self._speaker = speaker
        self._attr_name = f"Preset {presetNum}"
        self._preset = preset
        self.preset_num = presetNum
        self.config_entry = config_entry
        self._attr_icon = "mdi:folder-play"
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


class BoseBluetoothPairButton(BoseBaseEntity, ButtonEntity):
    """Button to enable Bluetooth pairing mode on Bose speakers."""

    def __init__(
        self,
        speaker: BoseSpeaker,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the Bluetooth pairing button."""
        BoseBaseEntity.__init__(self, speaker)
        self._speaker = speaker
        self.config_entry = config_entry
        self._attr_name = "Bluetooth Pairing"
        self._attr_translation_key = "bluetooth_pairing"
        self._attr_icon = "mdi:bluetooth"
        self._attr_entity_category = EntityCategory.CONFIG

    async def async_press(self, **kwargs) -> None:
        """Press the button to enable Bluetooth pairing."""
        _LOGGER.info("Enabling Bluetooth pairing mode")
        try:
            await self._speaker.set_bluetooth_sink_pairable()
        except (ConnectionError, TimeoutError) as err:
            _LOGGER.error("Failed to enable Bluetooth pairing: %s", err)
