"""Support for Bose adjustable sound settings (sliders)."""

from typing import Any

from pybose.BoseResponse import Audio
from pybose.BoseSpeaker import BoseSpeaker

from homeassistant.components.number import (
    ATTR_MAX,
    ATTR_MIN,
    ATTR_MODE,
    ATTR_STEP,
    ATTR_VALUE,
    NumberEntity,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import _LOGGER, DOMAIN

# Define adjustable sound parameters
ADJUSTABLE_PARAMETERS = [
    {
        "display": "Bass",
        "path": "/audio/bass",
        "option": "bass",
        "min": -100,
        "max": 100,
        "step": 10,
    },
    {
        "display": "Treble",
        "path": "/audio/treble",
        "option": "treble",
        "min": -100,
        "max": 100,
        "step": 10,
    },
    {
        "display": "Center",
        "path": "/audio/center",
        "option": "center",
        "min": -100,
        "max": 100,
        "step": 10,
    },
    {
        "display": "Subwoofer Gain",
        "path": "/audio/subwooferGain",
        "option": "subwooferGain",
        "min": -100,
        "max": 100,
        "step": 10,
    },
    {
        "display": "Height",
        "path": "/audio/height",
        "option": "height",
        "min": -100,
        "max": 100,
        "step": 10,
    },
    {
        "display": "AV Sync",
        "path": "/audio/avSync",
        "option": "avSync",
        "min": 0,
        "max": 200,
        "step": 10,
    },
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Bose number entities (sliders) for sound settings."""
    speaker: BoseSpeaker = hass.data[DOMAIN][config_entry.entry_id]["speaker"]

    # Fetch system info
    system_info = await speaker.get_system_info()

    entities = [
        BoseAudioSlider(speaker, system_info, config_entry, parameter, hass)
        for parameter in ADJUSTABLE_PARAMETERS
        if speaker.has_capability(parameter["path"])
    ]

    async_add_entities(entities)


class BoseAudioSlider(NumberEntity):
    """Representation of a Bose audio setting (Bass, Treble, Center, etc.) as a slider."""

    def __init__(
        self,
        speaker: BoseSpeaker,
        speaker_info,
        config_entry,
        parameter,
        hass: HomeAssistant,
    ) -> None:
        """Initialize the slider."""
        self.speaker = speaker
        self.speaker_info = speaker_info
        self.config_entry = config_entry
        self._attr_name = parameter.get("display")
        self._path = parameter.get("path")
        self._option = parameter.get("option")
        self._current_value = None
        self._attr_min_value = parameter.get("min")
        self._attr_max_value = parameter.get("max")
        self._attr_step = parameter.get("step")
        self._attr_native_min_value = parameter.get("min")
        self._attr_native_max_value = parameter.get("max")
        self._attr_native_step = parameter.get("step")
        self._attr_icon = "mdi:sine-wave"

        self._attr_entity_category = EntityCategory.CONFIG

        self._attr_unique_id = (
            f"{config_entry.data['guid']}_{self._attr_name.lower()}_slider"
        )

        self.speaker.attach_receiver(self._parse_message)

        hass.async_create_task(self.async_update())

    def _parse_message(self, data):
        """Parse the message from the speaker."""
        if data.get("header", {}).get("resource") == self._path:
            self._parse_audio(Audio(data.get("body")))

    def _parse_audio(self, data: Audio):
        self._current_value = data.get("value", 0)
        if self.hass:
            self.async_write_ha_state()

    async def async_update(self) -> None:
        """Fetch the current value of the setting."""
        self._parse_audio(await self.speaker.get_audio_setting(self._option))
        if self.hass:
            self.async_write_ha_state()

    async def async_set_value(self, value: float) -> None:
        """Set the new value for the setting."""
        try:
            await self.speaker.set_audio_setting(self._option, value)
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error(
                "Failed to set audio setting %s to %s: %s",
                self._option,
                value,
                e,
            )
            raise

    @property
    def value(self) -> float:
        """Return the current value of the setting."""
        return self._current_value

    @property
    def unique_id(self) -> str:
        """Return a unique ID for this entity."""
        return self._attr_unique_id

    @property
    def capability_attributes(self) -> dict[str, Any]:
        """Return capability attributes."""
        return {
            ATTR_MIN: self._attr_min_value,
            ATTR_MAX: self._attr_max_value,
            ATTR_STEP: self._attr_step,
            ATTR_VALUE: self._current_value,
            ATTR_MODE: NumberMode.SLIDER,
        }

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        return {
            "identifiers": {(DOMAIN, self.config_entry.data["guid"])},
        }
