import logging

from pybose.BoseResponse import Battery
from pybose.BoseSpeaker import BoseSpeaker

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from ..const import DOMAIN


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

        hass.async_create_task(self.async_update())

    async def async_update(self) -> None:
        """Fetch the latest battery status."""
        if not self.hass:
            return
        try:
            battery_status = await self.speaker.get_battery_status()
            self.update_from_battery_status(battery_status)
            self.async_write_ha_state()
        except Exception:  # noqa: BLE001
            logging.debug(
                "Error updating battery status for %s",
                self.config_entry.data["ip"],
            )
            logging.exception()
