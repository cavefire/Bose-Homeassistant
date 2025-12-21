"""Support for Bose battery and WiFi status sensors."""

from pybose import BoseSpeaker
from pybose.BoseResponse import Battery, WifiStatus

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import SIGNAL_STRENGTH_DECIBELS_MILLIWATT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .bose.battery import BoseBatteryBase
from .bose.wifi import BoseWifiBase
from .const import DOMAIN
from .entity import BoseBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Bose battery and WiFi sensors if supported."""
    speaker = hass.data[DOMAIN][config_entry.entry_id]["speaker"]
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]

    entities = []

    if speaker.has_capability("/system/battery"):
        entities.extend(
            [
                BoseBatteryLevelSensor(speaker, config_entry, hass, coordinator),
                BoseBatteryTimeTillEmpty(speaker, config_entry, hass, coordinator),
                BoseBatteryTimeTillFull(speaker, config_entry, hass, coordinator),
            ]
        )

    if speaker.has_capability("/network/wifi/status"):
        entities.extend(
            [
                BoseWifiSignalSensor(speaker, config_entry, hass, coordinator),
                BoseWifiSsidSensor(speaker, config_entry, hass, coordinator),
            ]
        )

    if entities:
        async_add_entities(entities, update_before_add=False)


class BoseBatteryLevelSensor(BoseBaseEntity, BoseBatteryBase, SensorEntity):
    """Sensor for battery level."""

    def __init__(
        self,
        speaker: BoseSpeaker,
        config_entry,
        hass: HomeAssistant,
        coordinator,
    ) -> None:
        """Initialize battery level sensor."""
        BoseBaseEntity.__init__(self, speaker)
        BoseBatteryBase.__init__(self, speaker, config_entry, hass, coordinator)
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
        coordinator,
    ) -> None:
        """Initialize charging state sensor."""
        BoseBaseEntity.__init__(self, speaker)
        BoseBatteryBase.__init__(self, speaker, config_entry, hass, coordinator)
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
        coordinator,
    ) -> None:
        """Initialize charging state sensor."""
        BoseBaseEntity.__init__(self, speaker)
        BoseBatteryBase.__init__(self, speaker, config_entry, hass, coordinator)
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


class BoseWifiSignalSensor(BoseBaseEntity, BoseWifiBase, SensorEntity):
    """Sensor for WiFi signal strength."""

    def __init__(
        self,
        speaker: BoseSpeaker,
        config_entry,
        hass: HomeAssistant,
        coordinator,
    ) -> None:
        """Initialize WiFi signal sensor."""
        BoseBaseEntity.__init__(self, speaker)
        BoseWifiBase.__init__(self, speaker, config_entry, hass, coordinator)
        self._attr_translation_key = "wifi_signal"
        self._attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
        self._attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_entity_category = None

    def update_from_wifi_status(self, wifi_status: WifiStatus):
        """Update sensor state."""
        self._attr_native_value = wifi_status.get("signalDbm")


class BoseWifiSsidSensor(BoseBaseEntity, BoseWifiBase, SensorEntity):
    """Sensor for WiFi SSID."""

    def __init__(
        self,
        speaker: BoseSpeaker,
        config_entry,
        hass: HomeAssistant,
        coordinator,
    ) -> None:
        """Initialize WiFi SSID sensor."""
        BoseBaseEntity.__init__(self, speaker)
        BoseWifiBase.__init__(self, speaker, config_entry, hass, coordinator)
        self._attr_translation_key = "wifi_ssid"
        self._attr_icon = "mdi:wifi"
        self._attr_entity_category = None

    def update_from_wifi_status(self, wifi_status: WifiStatus):
        """Update sensor state."""
        self._attr_native_value = wifi_status.get("ssid")
