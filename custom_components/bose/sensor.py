"""Support for Bose battery status sensor."""

from pybose import BoseSpeaker
from pybose.BoseResponse import Battery

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .bose.battery import BoseBatteryBase
from .const import DOMAIN


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
                BoseBatteryLevelSensor(speaker, config_entry, hass),
                BoseBatteryTimeTillEmpty(speaker, config_entry, hass),
                BoseBatteryTimeTillFull(speaker, config_entry, hass),
            ],
            update_before_add=False,
        )


class BoseBatteryLevelSensor(BoseBatteryBase, SensorEntity):
    """Sensor for battery level."""

    def __init__(
        self,
        speaker: BoseSpeaker,
        config_entry,
        hass: HomeAssistant,
    ) -> None:
        """Initialize battery level sensor."""
        super().__init__(speaker, config_entry, hass)
        self._attr_name = f"{config_entry.data['name']} Battery Level"
        self._attr_unique_id = f"{config_entry.data['guid']}_battery_level"
        self.native_unit_of_measurement = "%"
        self._attr_device_class = SensorDeviceClass.BATTERY

    def update_from_battery_status(self, battery_status: Battery):
        """Update sensor state."""
        self.native_value = battery_status.percent


class BoseBatteryTimeTillFull(BoseBatteryBase, SensorEntity):
    """Sensor for time till full charge."""

    def __init__(
        self,
        speaker: BoseSpeaker,
        config_entry,
        hass: HomeAssistant,
    ) -> None:
        """Initialize charging state sensor."""
        super().__init__(speaker, config_entry, hass)
        self._attr_name = f"{config_entry.data['name']} Time Till Full"
        self._attr_unique_id = f"{config_entry.data['guid']}_time_till_full"
        self._attr_device_class = SensorDeviceClass.DURATION
        self.native_unit_of_measurement = "min"

    def update_from_battery_status(self, battery_status: Battery):
        """Update sensor state."""
        if battery_status.minutesToFull == 65535:
            self.native_value = None
        else:
            self.native_value = battery_status.minutesToFull


class BoseBatteryTimeTillEmpty(BoseBatteryBase, SensorEntity):
    """Sensor for time till full charge."""

    def __init__(
        self,
        speaker: BoseSpeaker,
        config_entry,
        hass: HomeAssistant,
    ) -> None:
        """Initialize charging state sensor."""
        super().__init__(speaker, config_entry, hass)
        self._attr_name = f"{config_entry.data['name']} Time till empty"
        self._attr_unique_id = f"{config_entry.data['guid']}_time_till_empty"
        self._attr_device_class = SensorDeviceClass.DURATION
        self.native_unit_of_measurement = "min"

    def update_from_battery_status(self, battery_status: Battery):
        """Update sensor state."""
        if battery_status.minutesToEmpty == 65535:
            self.native_value = None
        else:
            self.native_value = battery_status.minutesToEmpty
