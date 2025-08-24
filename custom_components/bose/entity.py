"""Base entity for Bose integration."""

from typing import cast

from propcache.api import cached_property
from pybose.BoseSpeaker import BoseSpeaker

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class BoseBaseEntity(Entity):
    """Base entity for Bose integration."""

    def __init__(self, speaker: BoseSpeaker) -> None:
        """Initialize the entity."""
        self.speaker = speaker

        self._attr_has_entity_name = True

    @cached_property
    def device_info(self) -> DeviceInfo:
        """Return the device info of the entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, cast(str, self.speaker.get_device_id()))},
        )

    @cached_property
    def unique_id(self) -> str:
        """Return a unique ID for this entity."""
        base_id = cast(str, self.speaker.get_device_id())

        if (
            hasattr(self, "_attr_translation_key")
            and self._attr_translation_key is not None
            and self._attr_translation_key.strip()
        ):
            name_part = self._attr_translation_key.strip()
        elif (
            hasattr(self, "_attr_name")
            and self._attr_name is not None
            and self._attr_name.strip()
        ):
            name_part = self._attr_name.strip()
        else:
            name_part = "error"

        if not name_part:
            return base_id
        name_part = name_part.lower().replace(" ", "_")
        return f"{base_id}_{name_part}"
