"""Audio format helper mixin for Bose integration.

This module provides a small helper mixin used by audio format / codec
sensors. It intentionally does not inherit from Home Assistant Entity
classes to avoid multiple-inheritance conflicts.
"""

from pybose.BoseSpeaker import BoseSpeaker

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from ..const import _LOGGER, DOMAIN
from ..coordinator import BoseCoordinator


class BoseAudioFormatBase:
    """Helper mixin for Bose audio format / codec sensors."""

    def __init__(
        self,
        speaker: BoseSpeaker,
        config_entry: ConfigEntry,
        hass: HomeAssistant,
        coordinator: BoseCoordinator,
    ) -> None:
        """Initialize the audio format helper on the entity instance."""
        self.speaker = speaker
        self.config_entry = config_entry
        self.coordinator = coordinator
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.data["guid"])},
        }

        self.speaker.attach_receiver(self._parse_message)
        self.hass = hass

    def _parse_message(self, data):
        """Parse real-time audio format messages from the speaker."""
        if data.get("header", {}).get("resource") == "/audio/format":
            self.update_from_audio_format(data.get("body") or {})
            if self.hass and hasattr(self, "async_write_ha_state"):
                self.async_write_ha_state()

    def update_from_audio_format(self, body: dict):
        """Implemented in sensor."""
        raise NotImplementedError("update_from_audio_format not implemented in sensor")

    async def async_update(self) -> None:
        """Fetch the latest audio format from the cached speaker feed."""
        try:
            cached = self.coordinator.get_cached_data("/audio/format")
            if cached is not None:
                self.update_from_audio_format(cached)
        except Exception:  # noqa: BLE001
            _LOGGER.exception(
                "Error updating audio format for %s",
                self.config_entry.data.get("ip"),
            )
