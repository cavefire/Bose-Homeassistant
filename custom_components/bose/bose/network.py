"""Network helper mixin for Bose integration.

This module provides a small helper mixin used by network-related
entities. It intentionally does not inherit from Home Assistant
Entity classes to avoid multiple-inheritance conflicts.
"""

from pybose.BoseResponse import NetworkStatus
from pybose.BoseSpeaker import BoseSpeaker

from ..const import _LOGGER, DOMAIN
from ..coordinator import BoseCoordinator
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


class BoseNetworkBase:
    """Helper mixin for Bose network sensors."""

    def __init__(
        self,
        speaker: BoseSpeaker,
        config_entry: ConfigEntry,
        hass: HomeAssistant,
        coordinator: BoseCoordinator,
    ) -> None:
        """Initialize the network helper on the entity instance."""
        self.speaker = speaker
        self.config_entry = config_entry
        self.coordinator = coordinator
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.data["guid"])},
        }

        self.speaker.attach_receiver(self._parse_message)
        self.hass = hass

    def _parse_message(self, data):
        """Parse real-time messages from the speaker."""
        if data.get("header", {}).get("resource") == "/network/status":
            self.update_from_network_status(NetworkStatus(data.get("body")))
            if self.hass and hasattr(self, "async_write_ha_state"):
                self.async_write_ha_state()

    def update_from_network_status(self, network_status: NetworkStatus):
        """Implemented in sensor."""
        raise NotImplementedError(
            "update_from_network_status not implemented in sensor"
        )

    async def async_update(self) -> None:
        """Fetch the latest network status."""
        try:
            network_data = await self.coordinator.get_network_status()
            network_status = NetworkStatus(network_data)
            self.update_from_network_status(network_status)
        except Exception:  # noqa: BLE001
            _LOGGER.exception(
                "Error updating network status for %s", self.config_entry.data["ip"]
            )
