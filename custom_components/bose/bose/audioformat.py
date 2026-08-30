"""Audio format helper mixin for Bose integration.

This module provides a small helper mixin used by audio format / codec
sensors. It intentionally does not inherit from Home Assistant Entity
classes to avoid multiple-inheritance conflicts.
"""

from typing import Any

from pybose.BoseSpeaker import BoseSpeaker

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from ..const import _LOGGER
from ..coordinator import BoseCoordinator

AUDIO_FORMAT_RESOURCE = "/audio/format"


def format_audio_codec(body: dict[str, Any] | None) -> str | None:
    """Describe the audio format the speaker is currently decoding."""
    if not body:
        return None

    codec = body.get("format") or body.get("type")
    if not codec:
        return None

    channels = body.get("channels")
    return f"{codec} · {channels}" if channels else codec


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

        self.speaker.attach_receiver(self._parse_message)
        self.hass = hass

        hass.async_create_task(self.async_update())

    def _parse_message(self, data):
        """Parse real-time audio format messages from the speaker."""
        if data.get("header", {}).get("resource") == AUDIO_FORMAT_RESOURCE:
            self.update_from_audio_format(data.get("body") or {})
            self._write_state()

    def _write_state(self) -> None:
        """Write the state, but only once Home Assistant knows the entity."""
        if getattr(self, "hass", None) and getattr(self, "entity_id", None):
            self.async_write_ha_state()  # type: ignore[attr-defined]

    def update_from_audio_format(self, body: dict[str, Any]) -> None:
        """Implemented in sensor."""
        raise NotImplementedError("update_from_audio_format not implemented in sensor")

    async def async_update(self) -> None:
        """Fetch the latest audio format from the speaker."""
        if not getattr(self, "hass", None):
            return
        try:
            self.update_from_audio_format(await self.coordinator.get_audio_format())
            self._write_state()
        except Exception:  # noqa: BLE001
            _LOGGER.exception(
                "Error updating audio format for %s",
                self.config_entry.data.get("ip"),
            )
