"""Support for Bose adjustable sound settings (sliders)."""

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
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import _LOGGER, DOMAIN
from .entity import BoseBaseEntity

# Common parameters available on all non-Lifestyle Bose speakers
COMMON_PARAMETERS = [
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
        "display": "Height",
        "path": "/audio/height",
        "option": "height",
        "min": -100,
        "max": 100,
        "step": 10,
    },
    {
        "display": "Subwoofer Gain",
        "path": "/audio/subwooferGain",
        "option": "subwooferGain",
        "translation_key": "subwoofer_gain",
        "min": -100,
        "max": 100,
        "step": 10,
    },
    {
        "display": "Rear Speaker Gain",
        "path": "/audio/surround",
        "option": "surround",
        "min": -100,
        "max": 100,
        "step": 10,
    },
    {
        "display": "AV Sync",
        "path": "/audio/avSync",
        "option": "avSync",
        "translation_key": "av_sync",
        "min": 0,
        "max": 200,
        "step": 10,
    },
]

# Lifestyle (non-Ultra Soundbar) overrides: clamp to -10..10
LIFESTYLE_PARAMETERS = [
    {
        "display": "Bass",
        "path": "/audio/bass",
        "option": "bass",
        "min": -10,
        "max": 10,
        "step": 1,
    },
    {
        "display": "Treble",
        "path": "/audio/treble",
        "option": "treble",
        "min": -10,
        "max": 10,
        "step": 1,
    },
    {
        "display": "Center",
        "path": "/audio/center",
        "option": "center",
        "min": -10,
        "max": 10,
        "step": 1,
    },
    {
        "display": "Sub",
        "path": "/audio/subwooferGain",
        "option": "subwooferGain",
        "min": -10,
        "max": 10,
        "step": 1,
    },
    {
        "display": "Height",
        "path": "/audio/height",
        "option": "height",
        "min": -10,
        "max": 10,
        "step": 1,
    },
    {
        "display": "AV Sync",
        "path": "/audio/avSync",
        "option": "avSync",
        "translation_key": "av_sync",
        "min": 0,
        "max": 200,
        "step": 10,
    },
]

# Lifestyle Ultra Soundbar: names and order match the Bose app
LIFESTYLE_ULTRA_SOUNDBAR_PARAMETERS = [
    {
        "display": "Treble",
        "path": "/audio/treble",
        "option": "treble",
        "min": -10,
        "max": 10,
        "step": 1,
    },
    {
        "display": "Mids",
        "path": "/audio/midrange",
        "option": "midrange",
        "min": -10,
        "max": 10,
        "step": 1,
    },
    {
        "display": "Bass",
        "path": "/audio/bass",
        "option": "bass",
        "min": -10,
        "max": 10,
        "step": 1,
    },
    {
        "display": "Center",
        "path": "/audio/center",
        "option": "center",
        "min": -10,
        "max": 10,
        "step": 1,
    },
    {
        "display": "Height",
        "path": "/audio/height",
        "option": "height",
        "min": -10,
        "max": 10,
        "step": 1,
    },
    {
        "display": "Surround",
        "path": "/audio/systemSurroundLevel",
        "option": "systemSurroundLevel",
        "min": -10,
        "max": 10,
        "step": 1,
    },
    {
        "display": "Sub",
        "path": "/audio/subwooferGain",
        "option": "subwooferGain",
        "min": -10,
        "max": 10,
        "step": 1,
    },
    {
        "display": "AV Sync",
        "path": "/audio/avSync",
        "option": "avSync",
        "translation_key": "av_sync",
        "min": 0,
        "max": 200,
        "step": 10,
    },
]


def _is_lifestyle(product_name: str) -> bool:
    """Check if the product is a Bose Lifestyle product."""
    return "LS" in product_name


def _is_lifestyle_ultra_soundbar(product_name: str) -> bool:
    """Check if the product is a Lifestyle Ultra Soundbar."""
    return "LS Ultra Soundbar" in product_name


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Bose number entities (sliders) for sound settings."""
    speaker: BoseSpeaker = hass.data[DOMAIN][config_entry.entry_id]["speaker"]
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]

    # Fetch system info
    system_info = await speaker.get_system_info()
    product_name = system_info.get("productName", "")
    is_lifestyle = _is_lifestyle(product_name)
    is_ultra_sb = _is_lifestyle_ultra_soundbar(product_name)

    # Pick parameter list based on product type
    if is_ultra_sb:
        parameters = LIFESTYLE_ULTRA_SOUNDBAR_PARAMETERS
    elif is_lifestyle:
        parameters = LIFESTYLE_PARAMETERS
    else:
        parameters = COMMON_PARAMETERS

    entities = []
    for parameter in parameters:
        # Lifestyle Ultra Soundbar parameters are known to work via raw API
        # even though has_capability returns false for some of them
        if is_ultra_sb or speaker.has_capability(parameter["path"]):
            entities.append(
                BoseAudioSlider(
                    speaker, system_info, config_entry, parameter, hass, coordinator
                )
            )

    async_add_entities(entities)


class BoseAudioSlider(BoseBaseEntity, NumberEntity):
    """Representation of a Bose audio setting (Bass, Treble, Center, etc.) as a slider."""

    def __init__(
        self,
        speaker: BoseSpeaker,
        speaker_info,
        config_entry,
        parameter,
        hass: HomeAssistant,
        coordinator,
    ) -> None:
        """Initialize the slider."""
        BoseBaseEntity.__init__(self, speaker)
        self.speaker_info = speaker_info
        self.config_entry = config_entry
        self.coordinator = coordinator
        self._path = parameter.get("path")
        self._option = parameter.get("option")
        self._attr_native_value = None
        self._attr_min_value = parameter.get("min")
        self._attr_max_value = parameter.get("max")
        self._attr_step = parameter.get("step")
        self._attr_native_min_value = parameter.get("min")
        self._attr_native_max_value = parameter.get("max")
        self._attr_native_step = parameter.get("step")
        self._attr_icon = "mdi:sine-wave"
        self._attr_translation_key = parameter.get("translation_key", self._option)
        self._cf_unique_id = self._option
        self._attr_capability_attributes = {
            ATTR_MIN: self._attr_min_value,
            ATTR_MAX: self._attr_max_value,
            ATTR_STEP: self._attr_step,
            ATTR_VALUE: self._attr_native_value,
            ATTR_MODE: NumberMode.SLIDER,
        }

        self._attr_entity_category = EntityCategory.CONFIG

        self.speaker.attach_receiver(self._parse_message)

        hass.async_create_task(self.async_update())

    def _parse_message(self, data):
        """Parse the message from the speaker."""
        if data.get("header", {}).get("resource") == self._path:
            self._parse_audio(Audio(data.get("body")))

    def _parse_audio(self, data: Audio):
        self._attr_native_value = data.get("value", 0)
        if self.hass:
            self.async_write_ha_state()

    async def async_update(self) -> None:
        """Fetch the current value of the setting."""
        try:
            audio_dict = await self.coordinator.get_audio_setting(self._option)
        except Exception:
            _LOGGER.debug("pybose rejected %s, trying raw request", self._option)
            try:
                audio_dict = await self.speaker._request(self._path, "GET")  # noqa: SLF001
            except Exception:
                _LOGGER.warning("Cannot fetch %s via raw request", self._option)
                return
        self._parse_audio(Audio(audio_dict))
        if self.hass:
            self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        """Set the new value for the setting."""
        try:
            await self.speaker.set_audio_setting(self._option, int(value))
        except Exception:
            _LOGGER.debug("pybose rejected set %s, trying raw request", self._option)
            try:
                await self.speaker._request(  # noqa: SLF001
                    self._path, "POST", {"value": int(value)}
                )
            except Exception as e:
                _LOGGER.error(
                    "Failed to set audio setting %s to %s: %s",
                    self._option,
                    value,
                    e,
                )
                raise
        self.async_write_ha_state()
