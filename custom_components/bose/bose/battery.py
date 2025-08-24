"""Battery helper mixin for Bose integration.

This module provides a small helper mixin used by battery-related
entities. It intentionally does not inherit from Home Assistant
Entity classes to avoid multiple-inheritance conflicts.
"""

from typing import Any, cast

from pybose.BoseResponse import Battery
from pybose.BoseSpeaker import BoseSpeaker

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from ..const import _LOGGER, DOMAIN


def dummy_battery_status() -> Battery:
    """Return dummy battery status. Used for testing."""
    data = {
        "chargeStatus": "CHARGING",
        "chargerConnected": "CONNECTED",
        "minutesToEmpty": 433,
        "minutesToFull": 65535,
        "percent": 42,
        "sufficientChargerConnected": True,
        "temperatureState": "NORMAL",
    }
    return Battery(cast(Any, data))


class BoseBatteryBase:
    """Helper mixin for Bose battery sensors."""

    def __init__(
        self, speaker: BoseSpeaker, config_entry: ConfigEntry, hass: HomeAssistant
    ) -> None:
        """Initialize the battery helper on the entity instance."""
        self.speaker = speaker
        self.config_entry = config_entry
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.data["guid"])},
        }

        self.speaker.attach_receiver(self._parse_message)
        self.hass = hass

        hass.async_create_task(self.async_update())

    def _parse_message(self, data):
        """Parse real-time messages from the speaker."""
        if data.get("header", {}).get("resource") == "/system/battery":
            self.update_from_battery_status(Battery(data.get("body")))

    def update_from_battery_status(self, battery_status: Battery):
        """Implmented in sensor."""
        raise NotImplementedError(
            "update_from_battery_status not implemented in sensor"
        )

    async def async_update(self) -> None:
        """Fetch the latest battery status."""
        if not getattr(self, "hass", None):
            return
        try:
            battery_status = await self.speaker.get_battery_status()
            self.update_from_battery_status(battery_status)
            self.async_write_ha_state()
        except Exception:  # noqa: BLE001
            _LOGGER.exception(
                "Error updating battery status for %s", self.config_entry.data["ip"]
            )
