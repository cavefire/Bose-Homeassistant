"""Support for Bose battery status sensor."""

from pybose import BoseSpeaker
from pybose.BoseResponse import Battery

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .bose.battery import BoseBatteryBase
from .const import DOMAIN
from .entity import BoseBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Bose battery sensor if supported."""
    speaker = hass.data[DOMAIN][config_entry.entry_id]["speaker"]

    if speaker.has_capability("/system/battery"):
        async_add_entities(
            [
                BoseBatteryChargingSensor(speaker, None, config_entry, hass),
            ],
        )


class BoseBatteryChargingSensor(BoseBaseEntity, BoseBatteryBase, BinarySensorEntity):
    """Sensor for battery charging state."""

    def __init__(
        self,
        speaker: BoseSpeaker,
        battery_status: Battery | None,
        config_entry: ConfigEntry,
        hass: HomeAssistant,
    ) -> None:
        """Initialize charging state sensor."""
        # Initialize base entity and battery base
        BoseBaseEntity.__init__(self, speaker)
        BoseBatteryBase.__init__(self, speaker, config_entry, hass)
        self._attr_translation_key = "charging_state"
        self._attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING

        if battery_status is None:
            self._attr_available = False
        else:
            self.update_from_battery_status(battery_status)

    def update_from_battery_status(self, battery_status: Battery | None):
        """Update sensor state."""
        if not battery_status:
            self._attr_available = False
            return

        self._attr_available = True
        self.is_on = battery_status.get("chargerConnected", False) == "CONNECTED"
