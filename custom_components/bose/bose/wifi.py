"""WiFi helper mixin for Bose integration.

This module provides a small helper mixin used by WiFi-related
entities. It intentionally does not inherit from Home Assistant
Entity classes to avoid multiple-inheritance conflicts.
"""

from typing import Any, cast

from pybose.BoseResponse import WifiStatus
from pybose.BoseSpeaker import BoseSpeaker

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from ..const import _LOGGER, DOMAIN
from ..coordinator import BoseCoordinator


def dummy_wifi_status() -> WifiStatus:
    """Return dummy WiFi status. Used for testing."""
    data = {
        "frequencyKhz": 5180000,
        "signalDbm": -45,
        "signalDbmLevel": "EXCELLENT",
        "ssid": "MyNetwork",
        "state": "WIFI_STATION_CONNECTED",
    }
    return WifiStatus(cast(Any, data))


class BoseWifiBase:
    """Helper mixin for Bose WiFi sensors."""

    def __init__(
        self,
        speaker: BoseSpeaker,
        config_entry: ConfigEntry,
        hass: HomeAssistant,
        coordinator: BoseCoordinator,
    ) -> None:
        """Initialize the WiFi helper on the entity instance."""
        self.speaker = speaker
        self.config_entry = config_entry
        self.coordinator = coordinator
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.data["guid"])},
        }

        self.speaker.attach_receiver(self._parse_message)
        self.hass = hass

        hass.async_create_task(self.async_update())

    def _parse_message(self, data):
        """Parse real-time messages from the speaker."""
        if data.get("header", {}).get("resource") == "/network/wifi/status":
            self.update_from_wifi_status(WifiStatus(data.get("body")))

    def update_from_wifi_status(self, wifi_status: WifiStatus):
        """Implemented in sensor."""
        raise NotImplementedError("update_from_wifi_status not implemented in sensor")

    async def async_update(self) -> None:
        """Fetch the latest WiFi status."""
        if not getattr(self, "hass", None):
            return
        try:
            wifi_data = await self.coordinator.get_wifi_status()
            wifi_status = WifiStatus(wifi_data)
            self.update_from_wifi_status(wifi_status)
            self.async_write_ha_state()
        except Exception:  # noqa: BLE001
            _LOGGER.exception(
                "Error updating WiFi status for %s", self.config_entry.data["ip"]
            )
