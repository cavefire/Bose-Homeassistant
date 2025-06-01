"""Support for Bose battery status sensor."""

from pybose import BoseSpeaker
from pybose.BoseResponse import Battery

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import refresh_token
from .bose.battery import BoseBatteryBase
from .const import _LOGGER, DOMAIN


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

    async_add_entities(
        [
            BoseAuthValidTimeSensor(speaker, config_entry, hass),
        ]
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
        self.native_value = battery_status.get("percent", 0)


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
        self._attr_name = f"{config_entry.data['name']} Time till Full"
        self._attr_unique_id = f"{config_entry.data['guid']}_time_till_full"
        self._attr_device_class = SensorDeviceClass.DURATION
        self.native_unit_of_measurement = "min"

    def update_from_battery_status(self, battery_status: Battery):
        """Update sensor state."""
        if battery_status.get("minutesToFull") == 65535:
            if battery_status.get("percent", 0) == 100:
                self.native_value = 0
            self.native_value = None
        else:
            self.native_value = battery_status.get("minutesToFull", 0)


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
        if battery_status.get("minutesToEmpty") == 65535:
            if battery_status.get("percent", 0) == 0:
                self.native_value = 0
            self.native_value = None
        else:
            self.native_value = battery_status.get("minutesToEmpty")


class BoseAuthValidTimeSensor(SensorEntity):
    """Sensor for the auth valid time."""

    def __init__(
        self, speaker: BoseSpeaker, config_entry: ConfigEntry, hass: HomeAssistant
    ) -> None:
        """Initialize the auth valid time sensor."""
        self._config_entry = config_entry
        self._attr_name = f"{config_entry.data['name']} Auth Valid Time"
        self._attr_unique_id = f"{config_entry.data['guid']}_auth_valid_time"
        self._attr_icon = "mdi:clock"
        self.speaker = speaker
        self._hass = hass
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.data["guid"])},
        }
        self.entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> str:
        """Return the auth valid time in a human-readable format."""
        seconds_until_expire = self.speaker._bose_auth.get_token_validity_time()  # noqa: SLF001

        if seconds_until_expire < 300:
            _LOGGER.warning(
                "Refreshing token from sensor. This should not happen... Please open an issue"
            )
            self.hass.async_create_task(
                refresh_token(self.hass, self._config_entry, self.speaker._bose_auth)  # noqa: SLF001
            )

        if seconds_until_expire is None or seconds_until_expire <= 0:
            return None

        minutes, seconds = divmod(seconds_until_expire, 60)
        hours, minutes = divmod(minutes, 60)
        days, hours = divmod(hours, 24)

        if days > 0:
            return f"{days}d {hours}h {minutes}m {seconds}s"
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        if minutes > 0:
            return f"{minutes}m {seconds}s"
        return f"{seconds}s"
