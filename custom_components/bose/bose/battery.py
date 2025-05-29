from pybose.BoseResponse import Battery
from pybose.BoseSpeaker import BoseSpeaker

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

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
    return Battery(data)


class BoseBatteryBase(Entity):
    """Base class for Bose battery sensors."""

    def __init__(
        self, speaker: BoseSpeaker, config_entry: ConfigEntry, hass: HomeAssistant
    ) -> None:
        """Initialize the sensor."""
        self.speaker = speaker
        self.config_entry = config_entry
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.data["guid"])},
        }

        self.speaker.attach_receiver(self._parse_message)

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
        if not self.hass:
            return
        try:
            # battery_status = await self.speaker.get_battery_status()
            battery_status = dummy_battery_status()
            self.update_from_battery_status(battery_status)
            self.async_write_ha_state()
        except Exception:  # noqa: BLE001
            _LOGGER.exception(
                "Error updating battery status for %s", self.config_entry.data["ip"]
            )
