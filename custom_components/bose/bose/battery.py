from pybose.BoseResponse import Battery
from pybose.BoseSpeaker import BoseSpeaker

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
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

    def __init__(self, speaker: BoseSpeaker, config_entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        self.speaker = speaker
        self.config_entry = config_entry
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.data["guid"])},
            "name": config_entry.data["name"],
            "manufacturer": "Bose",
            "model": config_entry.data["serial"],
        }

    async def async_update(self) -> None:
        """Fetch the latest battery status."""
        if not self.hass:
            return
        try:
            battery_status = dummy_battery_status()
            self.update_from_battery_status(battery_status)
            self.async_write_ha_state()
        except Exception:  # noqa: BLE001
            pass


class BoseBatteryLevelSensor(BoseBatteryBase, SensorEntity):
    """Sensor for battery level."""

    def __init__(
        self, speaker: BoseSpeaker, battery_status: Battery, config_entry
    ) -> None:
        """Initialize battery level sensor."""
        super().__init__(speaker, config_entry)
        self._attr_name = f"{config_entry.data['name']} Battery Level"
        self._attr_unique_id = f"{config_entry.data['guid']}_battery_level"
        self.native_unit_of_measurement = "%"
        self._attr_device_class = SensorDeviceClass.BATTERY
        self.update_from_battery_status(battery_status)

    def update_from_battery_status(self, battery_status: Battery):
        """Update sensor state."""
        self.native_value = battery_status.percent


class BoseBatteryChargingSensor(BoseBatteryBase, BinarySensorEntity):
    """Sensor for battery charging state."""

    def __init__(
        self, speaker: BoseSpeaker, battery_status: Battery, config_entry
    ) -> None:
        """Initialize charging state sensor."""
        super().__init__(speaker, config_entry)
        self._attr_name = f"{config_entry.data['name']} Charging State"
        self._attr_unique_id = f"{config_entry.data['guid']}_charging_state"
        self._attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING
        self.update_from_battery_status(battery_status)

    def update_from_battery_status(self, battery_status: Battery):
        """Update sensor state."""
        self.is_on = battery_status.chargerConnected


class BoseBatteryTimeTillFull(BoseBatteryBase, SensorEntity):
    """Sensor for time till full charge."""

    def __init__(
        self, speaker: BoseSpeaker, battery_status: Battery, config_entry
    ) -> None:
        """Initialize charging state sensor."""
        super().__init__(speaker, config_entry)
        self._attr_name = f"{config_entry.data['name']} Time Till Full"
        self._attr_unique_id = f"{config_entry.data['guid']}_time_till_full"
        self._attr_device_class = SensorDeviceClass.DURATION
        self.native_unit_of_measurement = "min"
        self.update_from_battery_status(battery_status)

    def update_from_battery_status(self, battery_status: Battery):
        """Update sensor state."""
        if battery_status.minutesToFull == 65535:
            self.native_value = None
        else:
            self.native_value = battery_status.minutesToFull


class BoseBatteryTimeTillEmpty(BoseBatteryBase, SensorEntity):
    """Sensor for time till full charge."""

    def __init__(
        self, speaker: BoseSpeaker, battery_status: Battery, config_entry
    ) -> None:
        """Initialize charging state sensor."""
        super().__init__(speaker, config_entry)
        self._attr_name = f"{config_entry.data['name']} Time till empty"
        self._attr_unique_id = f"{config_entry.data['guid']}_time_till_empty"
        self._attr_device_class = SensorDeviceClass.DURATION
        self.native_unit_of_measurement = "min"
        self.update_from_battery_status(battery_status)

    def update_from_battery_status(self, battery_status: Battery):
        """Update sensor state."""
        if battery_status.minutesToEmpty == 65535:
            self.native_value = None
        else:
            self.native_value = battery_status.minutesToEmpty
