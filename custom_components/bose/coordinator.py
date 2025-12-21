"""Coordinator for Bose integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from pybose.BoseSpeaker import BoseSpeaker

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import _LOGGER, DOMAIN

# Cache expiry time in seconds
CACHE_EXPIRY_SECONDS = 60


@dataclass
class CachedMessage:
    """Represents a cached message from the speaker."""

    resource: str
    body: dict[str, Any]
    timestamp: datetime


@dataclass
class BoseCoordinatorData:
    """Data class for coordinator state."""

    cached_messages: dict[str, CachedMessage] = field(default_factory=dict)
    last_update: datetime | None = None


class BoseCoordinator(DataUpdateCoordinator[BoseCoordinatorData]):
    """Coordinator to manage Bose speaker data and caching."""

    def __init__(
        self,
        hass: HomeAssistant,
        speaker: BoseSpeaker,
        device_id: str,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{device_id}",
            update_interval=timedelta(minutes=5),
        )
        self.speaker = speaker
        self.device_id = device_id

        # Initialize with empty data
        self.data = BoseCoordinatorData()

        # Attach receiver to cache messages
        self.speaker.attach_receiver(self._cache_message)  # type: ignore[arg-type]

    def _cache_message(self, data: dict[str, Any] | Any) -> None:
        """Cache incoming messages from the speaker."""
        # Handle both dict and BoseMessage objects
        if not isinstance(data, dict):
            if hasattr(data, "to_dict"):
                data = data.to_dict()  # type: ignore[union-attr]
            elif hasattr(data, "__dict__"):
                data = data.__dict__
            else:
                _LOGGER.debug("Received non-dict message that couldn't be converted")
                return

        resource = data.get("header", {}).get("resource")
        body = data.get("body", {})

        if resource:
            cached = CachedMessage(
                resource=resource,
                body=body,
                timestamp=datetime.now(),
            )
            self.data.cached_messages[resource] = cached
            _LOGGER.debug("Cached message for resource: %s", resource)

    def _convert_to_dict(self, obj: Any) -> dict[str, Any]:
        """Convert pybose response objects to dict."""
        if isinstance(obj, dict):
            return obj
        try:
            return dict(obj)
        except (TypeError, ValueError):
            if hasattr(obj, "__dict__"):
                return obj.__dict__
            return {"value": obj}

    def _is_cache_valid(self, resource: str) -> bool:
        """Check if cached data for a resource is still valid."""
        if resource not in self.data.cached_messages:
            return False

        cached = self.data.cached_messages[resource]
        age = (datetime.now() - cached.timestamp).total_seconds()
        return age < CACHE_EXPIRY_SECONDS

    def get_cached_data(self, resource: str) -> dict[str, Any] | None:
        """Get cached data if available and valid."""
        if self._is_cache_valid(resource):
            _LOGGER.debug("Returning cached data for resource: %s", resource)
            return self.data.cached_messages[resource].body
        return None

    async def get_audio_volume(self) -> dict[str, Any]:
        """Get audio volume with caching."""
        resource = "/audio/volume"
        cached = self.get_cached_data(resource)
        if cached is not None:
            return cached

        _LOGGER.debug("Fetching fresh audio volume data")
        result = await self.speaker.get_audio_volume()
        result_dict = self._convert_to_dict(result)
        self._cache_message({"header": {"resource": resource}, "body": result_dict})
        return result_dict

    async def get_now_playing(self) -> dict[str, Any]:
        """Get now playing with caching."""
        resource = "/content/nowPlaying"
        cached = self.get_cached_data(resource)
        if cached is not None:
            return cached

        _LOGGER.debug("Fetching fresh now playing data")
        result = await self.speaker.get_now_playing()
        result_dict = self._convert_to_dict(result)
        self._cache_message({"header": {"resource": resource}, "body": result_dict})
        return result_dict

    async def get_battery_status(self) -> dict[str, Any]:
        """Get battery status with caching."""
        resource = "/system/battery"
        cached = self.get_cached_data(resource)
        if cached is not None:
            return cached

        _LOGGER.debug("Fetching fresh battery status data")
        result = await self.speaker.get_battery_status()
        result_dict = self._convert_to_dict(result)
        self._cache_message({"header": {"resource": resource}, "body": result_dict})
        return result_dict

    async def get_bluetooth_sink_status(self) -> dict[str, Any]:
        """Get Bluetooth sink status with caching."""
        resource = "/bluetooth/sink/status"
        cached = self.get_cached_data(resource)
        if cached is not None:
            return cached

        _LOGGER.debug("Fetching fresh Bluetooth sink status data")
        result = await self.speaker.get_bluetooth_sink_status()
        result_dict = self._convert_to_dict(result)
        self._cache_message({"header": {"resource": resource}, "body": result_dict})
        return result_dict

    async def get_bluetooth_sink_list(self) -> dict[str, Any]:
        """Get Bluetooth sink list with caching."""
        resource = "/bluetooth/sink/list"
        cached = self.get_cached_data(resource)
        if cached is not None:
            return cached

        _LOGGER.debug("Fetching fresh Bluetooth sink list data")
        result = await self.speaker.get_bluetooth_sink_list()
        result_dict = self._convert_to_dict(result)
        self._cache_message({"header": {"resource": resource}, "body": result_dict})
        return result_dict

    async def get_bluetooth_source_status(self) -> dict[str, Any]:
        """Get Bluetooth source status with caching."""
        resource = "/bluetooth/source/status"
        cached = self.get_cached_data(resource)
        if cached is not None:
            return cached

        _LOGGER.debug("Fetching fresh Bluetooth source status data")
        result = await self.speaker.get_bluetooth_source_status()
        result_dict = self._convert_to_dict(result)
        self._cache_message({"header": {"resource": resource}, "body": result_dict})
        return result_dict

    async def get_wifi_status(self) -> dict[str, Any]:
        """Get WiFi status with caching."""
        resource = "/network/wifi/status"
        cached = self.get_cached_data(resource)
        if cached is not None:
            return cached

        _LOGGER.debug("Fetching fresh WiFi status data")
        result = await self.speaker.get_wifi_status()
        result_dict = self._convert_to_dict(result)
        self._cache_message({"header": {"resource": resource}, "body": result_dict})
        return result_dict

    async def get_active_groups(self) -> list[dict[str, Any]]:
        """Get active groups with caching."""
        resource = "/grouping/activeGroups"
        cached = self.get_cached_data(resource)
        if cached is not None:
            return cached.get("activeGroups", [])

        _LOGGER.debug("Fetching fresh active groups data")
        result = await self.speaker.get_active_groups()
        result_list = [self._convert_to_dict(item) for item in result]
        self._cache_message(
            {
                "header": {"resource": resource},
                "body": {"activeGroups": result_list},
            }
        )
        return result_list

    async def get_sources(self) -> dict[str, Any]:
        """Get sources (not cached, as it's needed less frequently)."""
        result = await self.speaker.get_sources()
        return self._convert_to_dict(result)

    async def get_audio_setting(self, option: str) -> dict[str, Any]:
        """Get audio setting with caching."""
        resource = f"/audio/{option}"
        cached = self.get_cached_data(resource)
        if cached is not None:
            return cached

        _LOGGER.debug("Fetching fresh audio setting data for %s", option)
        result = await self.speaker.get_audio_setting(option)
        result_dict = dict(result) if hasattr(result, "__iter__") else {"value": result}
        self._cache_message({"header": {"resource": resource}, "body": result_dict})
        return result_dict

    async def _async_update_data(self) -> BoseCoordinatorData:
        """Fetch data from speaker."""
        self.data.last_update = datetime.now()
        return self.data
