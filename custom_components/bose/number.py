"""Support for Bose adjustable sound settings (sliders)."""

import asyncio
import re

from pybose.BoseResponse import Audio
from pybose.BoseSpeaker import BoseSpeaker

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import _LOGGER, DOMAIN
from .entity import BoseBaseEntity

# Speakers do not always list every sound setting they support, so the missing ones are still tried once.
# A speaker stays quiet about a setting it does not have, so that probe gets a shorter timeout than usual to keep set-up quick.
PROBE_TIMEOUT = 5

# The sound settings that are sliders. Which of these a speaker actually has,
# what they range over and how far each step goes is read from the speaker.
AUDIO_SLIDERS = (
    "bass",
    "midrange",
    "treble",
    "center",
    "height",
    "surround",
    "systemSurroundLevel",
    "subwooferGain",
    "avSync",
)

# Last resort for a speaker that reports a setting without a range of its own.
FALLBACK_RANGES = {"avSync": (0, 200, 10)}
FALLBACK_RANGE = (-100, 100, 10)


def translation_key(option: str) -> str:
    """Return the translation key for a sound setting.

    Options are camelCase, translation keys are snake_case:
    subwooferGain -> subwoofer_gain.
    """
    return re.sub(r"(?<!^)(?=[A-Z])", "_", option).lower()


async def read_setting(speaker: BoseSpeaker, option: str) -> Audio | None:
    """Read a sound setting, or return None if the speaker does not have it.

    The capability check is left to the speaker itself: pybose refuses both
    resources a speaker does not advertise and settings pybose does not know
    about, and some speakers leave working settings out of their capabilities.
    """
    resource = f"/audio/{option}"
    advertised = speaker.has_capability(resource)
    try:
        audio = await speaker._request(  # noqa: SLF001
            resource,
            "GET",
            checkCapabilities=False,
            timeout=None if advertised else PROBE_TIMEOUT,
        )
    except Exception:  # noqa: BLE001
        _LOGGER.debug("Speaker has no %s", resource, exc_info=True)
        return None

    # Guard against reading something that is not a slider at all. bool is an
    # int as far as Python is concerned, hence the exact type check.
    if not isinstance(audio, dict) or type(audio.get("value")) is not int:
        _LOGGER.debug("Ignoring %s, it is not a numeric setting: %s", resource, audio)
        return None

    return Audio(audio)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Bose number entities (sliders) for sound settings."""
    speaker: BoseSpeaker = hass.data[DOMAIN][config_entry.entry_id]["speaker"]
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]

    # Ask the speaker which settings it has, all at once so an unanswered
    # probe does not hold up the others.
    settings = await asyncio.gather(
        *(read_setting(speaker, option) for option in AUDIO_SLIDERS)
    )

    async_add_entities(
        BoseAudioSlider(speaker, config_entry, option, audio, coordinator)
        for option, audio in zip(AUDIO_SLIDERS, settings, strict=True)
        if audio is not None
    )


class BoseAudioSlider(BoseBaseEntity, NumberEntity):
    """Representation of a Bose audio setting (Bass, Treble, Center, etc.) as a slider."""

    _attr_mode = NumberMode.SLIDER
    _attr_icon = "mdi:sine-wave"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        speaker: BoseSpeaker,
        config_entry: ConfigEntry,
        option: str,
        audio: Audio,
        coordinator,
    ) -> None:
        """Initialize the slider from what the speaker reported."""
        BoseBaseEntity.__init__(self, speaker)
        self.config_entry = config_entry
        self.coordinator = coordinator
        self._option = option
        self._path = f"/audio/{option}"
        self._attr_translation_key = translation_key(option)
        self._cf_unique_id = option

        (
            self._attr_native_min_value,
            self._attr_native_max_value,
            self._attr_native_step,
        ) = FALLBACK_RANGES.get(option, FALLBACK_RANGE)

        self._parse_audio(audio)

        self.speaker.attach_receiver(self._parse_message)

    def _parse_message(self, data):
        """Parse the message from the speaker."""
        if data.get("header", {}).get("resource") == self._path:
            self._parse_audio(Audio(data.get("body") or {}))

    def _parse_audio(self, data: Audio) -> None:
        """Store the value and the range the speaker reports alongside it."""
        self._attr_native_value = data.get("value", 0)

        properties = data.get("properties") or {}
        if (minimum := properties.get("min")) is not None:
            self._attr_native_min_value = minimum
        if (maximum := properties.get("max")) is not None:
            self._attr_native_max_value = maximum
        if step := properties.get("step"):
            self._attr_native_step = step

        self._attr_available = True
        self._write_state()

    def _write_state(self) -> None:
        """Write the state, but only once Home Assistant knows the entity."""
        if self.hass is not None and self.entity_id:
            self.async_write_ha_state()

    async def async_update(self) -> None:
        """Fetch the current value of the setting."""
        try:
            audio = Audio(await self.coordinator.get_audio_setting(self._option))
        except Exception:  # noqa: BLE001
            _LOGGER.debug(
                "pybose rejected reading %s, asking the speaker directly",
                self._option,
                exc_info=True,
            )
            audio = await read_setting(self.speaker, self._option)

        if audio is None:
            _LOGGER.warning(
                "Cannot read audio setting %s from %s",
                self._option,
                self.config_entry.data.get("ip"),
            )
            if self._attr_available:
                self._attr_available = False
                self._write_state()
            return

        self._parse_audio(audio)

    async def async_set_native_value(self, value: float) -> None:
        """Set the new value for the setting."""
        try:
            await self.speaker.set_audio_setting(self._option, int(value))
        except Exception:  # noqa: BLE001
            _LOGGER.debug(
                "pybose rejected writing %s, asking the speaker directly",
                self._option,
                exc_info=True,
            )
            try:
                await self.speaker._request(  # noqa: SLF001
                    self._path,
                    "POST",
                    {"value": int(value)},
                    checkCapabilities=False,
                )
            except Exception as e:
                _LOGGER.error(
                    "Failed to set audio setting %s to %s: %s",
                    self._option,
                    value,
                    e,
                )
                raise

        self._attr_native_value = int(value)
        self._attr_available = True
        self._write_state()
