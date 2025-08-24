"""Support for Bose battery status sensor."""

from pybose import BoseSpeaker
from pybose.BoseResponse import Battery

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
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
                BoseBatteryLevelSensor(speaker, config_entry, hass),
                BoseBatteryTimeTillEmpty(speaker, config_entry, hass),
                BoseBatteryTimeTillFull(speaker, config_entry, hass),
            ],
            update_before_add=False,
        )


class BoseBatteryLevelSensor(BoseBaseEntity, BoseBatteryBase, SensorEntity):
    """Sensor for battery level."""

    def __init__(
        self,
        speaker: BoseSpeaker,
        config_entry,
        hass: HomeAssistant,
    ) -> None:
        """Initialize battery level sensor."""
        BoseBaseEntity.__init__(self, speaker)
        BoseBatteryBase.__init__(self, speaker, config_entry, hass)
        self._attr_translation_key = "battery_level"
        self._attr_native_unit_of_measurement = "%"
        self._attr_device_class = SensorDeviceClass.BATTERY

    def update_from_battery_status(self, battery_status: Battery):
        """Update sensor state."""
        self._attr_native_value = battery_status.get("percent", 0)


class BoseBatteryTimeTillFull(BoseBaseEntity, BoseBatteryBase, SensorEntity):
    """Sensor for time till full charge."""

    def __init__(
        self,
        speaker: BoseSpeaker,
        config_entry,
        hass: HomeAssistant,
    ) -> None:
        """Initialize charging state sensor."""
        BoseBaseEntity.__init__(self, speaker)
        BoseBatteryBase.__init__(self, speaker, config_entry, hass)
        self._attr_translation_key = "time_till_full"
        self._attr_device_class = SensorDeviceClass.DURATION
        self._attr_native_unit_of_measurement = "min"

    def update_from_battery_status(self, battery_status: Battery):
        """Update sensor state."""
        if battery_status.get("minutesToFull") == 65535:
            if battery_status.get("percent", 0) == 100:
                self._attr_native_value = 0
            else:
                self._attr_native_value = None
        else:
            self._attr_native_value = battery_status.get("minutesToFull", 0)


class BoseBatteryTimeTillEmpty(BoseBaseEntity, BoseBatteryBase, SensorEntity):
    """Sensor for time till full charge."""

    def __init__(
        self,
        speaker: BoseSpeaker,
        config_entry,
        hass: HomeAssistant,
    ) -> None:
        """Initialize charging state sensor."""
        BoseBaseEntity.__init__(self, speaker)
        BoseBatteryBase.__init__(self, speaker, config_entry, hass)
        self._attr_translation_key = "time_till_empty"
        self._attr_device_class = SensorDeviceClass.DURATION
        self._attr_native_unit_of_measurement = "min"

    def update_from_battery_status(self, battery_status: Battery):
        """Update sensor state."""
        if battery_status.get("minutesToEmpty") == 65535:
            if battery_status.get("percent", 0) == 0:
                self._attr_native_value = 0
            else:
                self._attr_native_value = None
        else:
            self._attr_native_value = battery_status.get("minutesToEmpty")
