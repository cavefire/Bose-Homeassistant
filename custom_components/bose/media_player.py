"""Support for Bose media player."""

import asyncio
import functools
from typing import Any

import pychromecast
from pychromecast import discovery
from pychromecast.discovery import CastBrowser, SimpleCastListener

from pybose.BoseResponse import (
    AudioVolume,
    BluetoothSinkList,
    BluetoothSinkStatus,
    BluetoothSourceStatus,
    ContentNowPlaying,
    SystemInfo,
)
from pybose.BoseSpeaker import BoseSpeaker

from homeassistant.components import media_source, zeroconf
from homeassistant.components.media_player import (
    BrowseMedia,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    async_process_play_media_url,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
import homeassistant.helpers.entity_registry as er
from homeassistant.util import dt as dt_util

from .const import _LOGGER, DOMAIN
from .entity import BoseBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Bose media player."""
    speaker = hass.data[DOMAIN][config_entry.entry_id]["speaker"]
    system_info = hass.data[DOMAIN][config_entry.entry_id]["system_info"]

    async_add_entities(
        [BoseMediaPlayer(speaker, system_info, hass)], update_before_add=False
    )


class BoseMediaPlayer(BoseBaseEntity, MediaPlayerEntity):
    """Representation of a Bose speaker as a media player."""

    def __init__(
        self,
        speaker: BoseSpeaker,
        system_info: SystemInfo,
        hass: HomeAssistant,
    ) -> None:
        """Initialize the Bose media player."""
        BoseBaseEntity.__init__(self, speaker)
        self.speaker = speaker
        self.hass = hass
        self._device_id = speaker.get_device_id()
        self._is_on = False
        self._attr_state = MediaPlayerState.OFF
        self._attr_volume_level = 0.5
        self._attr_is_volume_muted = False
        self._attr_source = None
        self._attr_media_image_url = None
        self._attr_media_title = None
        self._attr_media_artist = None
        self._attr_media_album_name = None
        self._attr_media_duration = None
        self._attr_media_position = None
        self._attr_media_position_updated_at = None
        self._now_playing_result = ContentNowPlaying({})
        self._attr_group_members = []
        self._attr_source_list: list[str] = []
        self._active_group_id = None
        self._attr_translation_key = "media_player"
        self._cf_unique_id = system_info["name"]
        self._available_sources: dict[str, dict] = {
            "Optical": {"source": "PRODUCT", "sourceAccount": "AUX_DIGITAL"},
            "Cinch": {"source": "PRODUCT", "sourceAccount": "AUX_ANALOG"},
            "TV": {"source": "PRODUCT", "sourceAccount": "TV"},
        }
        self._bluetooth_devices: dict[str, dict] = {}
        self._chromecast_device = None
        self._media_controller = None
        self._speaker_ip = None

        config_data = hass.data[DOMAIN].get(
            hass.config_entries.async_entries(DOMAIN)[0].entry_id, {}
        )
        if "config" in config_data and "ip" in config_data["config"]:
            self._speaker_ip = config_data["config"]["ip"]

        speaker.attach_receiver(self.parse_message)

        hass.async_create_task(self.async_update())

        if "media_entities" not in hass.data[DOMAIN]:
            hass.data[DOMAIN]["media_entities"] = {}
        hass.data[DOMAIN]["media_entities"][system_info.get("guid")] = self

        hass.async_create_task(self._async_setup_chromecast())

    def parse_message(self, data):
        """Parse the message from the speaker."""

        resource = data.get("header", {}).get("resource")
        body = data.get("body", {})
        if resource == "/audio/volume":
            self._parse_audio_volume(AudioVolume(body))
        elif resource == "/system/power/control":
            self._is_on = body.get("power") == "ON"
            if not self._is_on:
                self._attr_state = MediaPlayerState.OFF
        elif resource == "/content/nowPlaying":
            self._parse_now_playing(ContentNowPlaying(body))
        elif resource == "/grouping/activeGroups":
            self._parse_grouping(body)
        elif resource == "/bluetooth/sink/list":
            self._parse_bluetooth_sink_list(BluetoothSinkList(body))
        elif resource == "/bluetooth/sink/status":
            self._parse_bluetooth_sink_status(BluetoothSinkStatus(body))
        elif resource == "/bluetooth/source/status":
            self._parse_bluetooth_source_status(BluetoothSourceStatus(body))

        self.async_write_ha_state()

    def _parse_grouping(self, data: dict):
        active_groups = data.get("activeGroups", {})

        if len(active_groups) == 0:
            self._attr_group_members = []
            self._active_group_id = None
            return

        active_group = active_groups[0]

        guids = [
            product.get("productId", None) for product in active_group.get("products")
        ]

        if len(guids) == 0:
            self._attr_group_members = []
            self._active_group_id = None
            return

        guids.sort(
            key=lambda guid: guid == active_group.get("groupMasterId"), reverse=True
        )

        entity_ids = [
            self.hass.data[DOMAIN]["media_entities"][guid].entity_id for guid in guids
        ]

        self._attr_group_members = entity_ids
        self._active_group_id = active_group.get("activeGroupId")

    def _parse_audio_volume(self, data: AudioVolume):
        self._attr_volume_level = data.get("value", 0) / 100
        self._attr_is_volume_muted = data.get("muted")

    def _parse_now_playing(self, data: ContentNowPlaying):
        try:
            status = data.get("state", {}).get("status")
            match status:
                case "PLAY":
                    self._attr_state = MediaPlayerState.PLAYING
                case "PAUSED":
                    self._attr_state = MediaPlayerState.PAUSED
                case "BUFFERING":
                    self._attr_state = MediaPlayerState.BUFFERING
                case "STOPPED" | None:
                    if self._is_on:
                        self._attr_state = MediaPlayerState.IDLE
                    else:
                        self._attr_state = MediaPlayerState.OFF
                case _:
                    _LOGGER.warning("State not implemented: %s", status)
                    self._attr_state = MediaPlayerState.ON
        except AttributeError:
            self._attr_state = MediaPlayerState.ON

        self._attr_source = data.get("source", {}).get("sourceDisplayName", None)

        if  self._attr_source == "Chromecast Built-in":
           return
        
        self._attr_media_title = data.get("metadata", {}).get("trackName")
        self._attr_media_artist = data.get("metadata", {}).get("artist")
        self._attr_media_album_name = data.get("metadata", {}).get("album")
        self._attr_media_duration = int(data.get("metadata", {}).get("duration", 999))
        self._attr_media_position = int(data.get("state", {}).get("timeIntoTrack", 0))
        self._attr_media_position_updated_at = dt_util.utcnow()

        self._now_playing_result: ContentNowPlaying = data

        if (
            data.get("container", {}).get("contentItem", {}).get("source") == "PRODUCT"
            and data.get("container", {}).get("contentItem", {}).get("sourceAccount")
            == "TV"
        ):
            self._attr_source = "TV"
            self._attr_media_title = "TV"
            self._attr_media_album_name = None
            self._attr_media_artist = None
            self._attr_media_duration = None
            self._attr_media_position = None
        self._attr_media_image_url = (
            data.get("track", {}).get("contentItem", {}).get("containerArt")
        )

        if data.get("source", {}).get("sourceID") == "BLUETOOTH":
            # Fetch active Bluetooth device asynchronously to avoid using await in sync parser
            if getattr(self, "hass", None) is not None:
                self.hass.async_create_task(
                    self._async_update_active_bluetooth_source()
                )
        else:
            for name, source_data in self._available_sources.items():
                if data.get("container", {}).get("contentItem", {}).get(
                    "source"
                ) == source_data.get("source"):
                    if source_data.get("source") in ("SPOTIFY", "AMAZON", "DEEZER"):
                        if data.get("container", {}).get("contentItem", {}).get(
                            "sourceAccount"
                        ) != source_data.get("accountId"):
                            continue
                    elif source_data.get("sourceAccount") != data.get(
                        "container", {}
                    ).get("contentItem", {}).get("sourceAccount"):
                        continue

                    self._attr_source = name
                    break

    def _parse_bluetooth_sink_list(self, data: BluetoothSinkList) -> None:
        """Parse Bluetooth sink list."""
        devices = data.get("devices", [])
        for device in devices:
            mac = device.get("mac", "")
            name = device.get("name", "Unknown Device")
            if mac:
                self._bluetooth_devices[mac] = {
                    "name": name,
                    "mac": mac,
                    "device_class": device.get("deviceClass", ""),
                    "type": "sink",
                }

    def _parse_bluetooth_sink_status(self, data: BluetoothSinkStatus) -> None:
        """Parse Bluetooth sink status."""
        active_device = data.get("activeDevice")

        # Update Bluetooth devices from status
        devices = data.get("devices", [])
        for device in devices:
            mac = device.get("mac", "")
            name = device.get("name", "Unknown Device")
            if mac:
                self._bluetooth_devices[mac] = {
                    "name": name,
                    "mac": mac,
                    "device_class": device.get("deviceClass", ""),
                    "type": "sink",
                    "active": mac == active_device,
                }

        # Update source list with Bluetooth devices
        self._update_bluetooth_source_list()

        # Update current source if a Bluetooth device is active
        if active_device and active_device in self._bluetooth_devices:
            bluetooth_device = self._bluetooth_devices[active_device]
            self._attr_source = f"Bluetooth: {bluetooth_device['name']}"

    def _parse_bluetooth_source_status(self, data: BluetoothSourceStatus) -> None:
        """Parse Bluetooth source status."""
        devices = data.get("devices", [])
        for device in devices:
            mac = device.get("mac", "")
            name = device.get("name", "Unknown Device")
            if mac:
                self._bluetooth_devices[mac] = {
                    "name": name,
                    "mac": mac,
                    "device_class": device.get("deviceClass", ""),
                    "type": "source",
                }

        # Update source list with Bluetooth devices
        self._update_bluetooth_source_list()

    def _update_bluetooth_source_list(self) -> None:
        """Update the source list with Bluetooth devices."""
        # Remove old Bluetooth sources
        self._attr_source_list = [  # pyright: ignore[reportIncompatibleVariableOverride]
            source
            for source in self._attr_source_list
            if not source.startswith("Bluetooth:")
        ]

        # Add Bluetooth devices to source list
        for device in self._bluetooth_devices.values():
            bluetooth_source = f"Bluetooth: {device['name']}"
            if bluetooth_source not in self._attr_source_list:
                self._attr_source_list.append(bluetooth_source)

    async def _async_update_active_bluetooth_source(self) -> None:
        """Async helper to fetch active Bluetooth device and update source."""
        try:
            status = await self.speaker.get_bluetooth_sink_status()
        except (ConnectionError, TimeoutError) as err:
            _LOGGER.debug("Failed to fetch active Bluetooth device: %s", err)
            return

        active_device = None
        ad = None
        if isinstance(status, dict):
            ad = status.get("activeDevice")
        else:
            get_fn = getattr(status, "get", None)
            if callable(get_fn):
                try:
                    ad = get_fn("activeDevice")
                except Exception:  # noqa: BLE001
                    ad = None

        active_device = ad if isinstance(ad, str) else None

        if active_device and active_device in self._bluetooth_devices:
            bluetooth_device = self._bluetooth_devices[active_device]
            self._attr_source = f"Bluetooth: {bluetooth_device['name']}"
            self.async_write_ha_state()
            self._attr_source_list.append(self._attr_source)

    async def async_update(self) -> None:
        """Fetch new state data from the speaker."""
        data = await self.speaker.get_now_playing()
        self._parse_now_playing(data)

        data = await self.speaker.get_audio_volume()
        self._parse_audio_volume(data)

        # Refresh Bluetooth information
        try:
            bluetooth_sink_status = await self.speaker.get_bluetooth_sink_status()
            self._parse_bluetooth_sink_status(bluetooth_sink_status)

            bluetooth_sink_list = await self.speaker.get_bluetooth_sink_list()
            self._parse_bluetooth_sink_list(bluetooth_sink_list)

            bluetooth_source_status = await self.speaker.get_bluetooth_source_status()
            self._parse_bluetooth_source_status(bluetooth_source_status)
        except (ConnectionError, TimeoutError) as err:
            _LOGGER.debug("Failed to get Bluetooth information: %s", err)

        # Refresh available sources (build human readable list)
        sources = await self.speaker.get_sources()
        for source in sources.get("sources", []):
            if (
                (
                    source.get("status", None) in ("AVAILABLE", "NOT_CONFIGURED")
                    or source.get("accountId", "TV")
                )
                and source.get("sourceAccountName", None)
                and source.get("sourceName", None)
            ):
                if source.get("sourceName", None) in (
                    "AMAZON",
                    "SPOTIFY",
                    "DEEZER",
                ) and source.get("sourceAccountName", None) not in (
                    "AlexaUserName",
                    "SpotifyConnectUserName",
                    "DeezerUserName",
                ):
                    display = f"{source.get('sourceName', None).capitalize()}: {source.get('sourceAccountName', None)}"
                    self._available_sources[display] = {
                        "source": source.get("sourceName", None),
                        "sourceAccount": source.get("sourceAccountName", None),
                        "accountId": source.get("accountId", None),
                    }

                for key, value in self._available_sources.items():
                    if (
                        source.get("sourceName", None) == value["source"]
                        and source.get("sourceAccountName", None)
                        == value["sourceAccount"]
                    ):
                        if key not in self._attr_source_list:
                            self._attr_source_list.append(key)

        active_groups = await self.speaker.get_active_groups()
        self._parse_grouping({"activeGroups": active_groups})
        self.async_write_ha_state()

    async def async_select_source(self, source: str) -> None:
        """Select an input source on the speaker."""
        # Check if it's a Bluetooth source
        if source.startswith("Bluetooth:"):
            device_name = source.replace("Bluetooth: ", "")
            # Find the device by name
            for device in self._bluetooth_devices.values():
                if device["name"] == device_name:
                    try:
                        await self.speaker.connect_bluetooth_sink_device(device["mac"])
                        self._attr_source = source
                        self.async_write_ha_state()
                    except (ConnectionError, TimeoutError) as err:
                        raise ServiceValidationError(
                            translation_domain=DOMAIN,
                            translation_key="bluetooth_connect_failed",
                            translation_placeholders={
                                "device_name": device_name,
                                "error": str(err),
                            },
                        ) from err
                    return
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="bluetooth_device_not_found",
                translation_placeholders={"device_name": device_name},
            )

        # Handle regular sources
        if source not in self._available_sources:
            return

        source_data = self._available_sources[source]

        if not source_data.get("source") or not source_data.get("sourceAccount"):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="source_not_configured",
                translation_placeholders={"source_name": source},
            )

        result = await self.speaker.set_source(
            source_data.get("source", ""), source_data.get("sourceAccount", "")
        )
        self._parse_now_playing(ContentNowPlaying(result))

    async def async_turn_on(self) -> None:
        """Turn on the speaker."""
        await self.speaker.set_power_state(True)
        self._is_on = True
        self._attr_state = MediaPlayerState.IDLE
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        """Turn off the speaker."""
        await self.speaker.set_power_state(False)
        self._is_on = False
        self._attr_state = MediaPlayerState.OFF
        self.async_write_ha_state()

    async def async_media_stop(self) -> None:
        """Stop the playback."""
        await self.speaker.pause()
        self._attr_state = MediaPlayerState.IDLE
        self.async_write_ha_state()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level (0.0 to 1.0)."""
        await self.speaker.set_audio_volume(int(volume * 100))
        self._attr_volume_level = volume
        self.async_write_ha_state()

    async def async_mute_volume(self, mute: bool) -> None:
        """Send mute command."""
        await self.speaker.set_audio_volume_muted(mute)
        self._attr_is_volume_muted = mute
        self.async_write_ha_state()

    async def async_media_play(self) -> None:
        """Play the current media."""
        await self.speaker.play()
        self._attr_state = MediaPlayerState.PLAYING
        self.async_write_ha_state()

    async def async_media_pause(self) -> None:
        """Pause the current media."""
        await self.speaker.pause()
        self._attr_state = MediaPlayerState.PAUSED
        self.async_write_ha_state()

    async def async_media_next_track(self) -> None:
        """Skip to the next track."""
        await self.speaker.skip_next()
        self.async_write_ha_state()

    async def async_media_previous_track(self) -> None:
        """Skip to the previous track."""
        await self.speaker.skip_previous()
        self.async_write_ha_state()

    async def async_media_seek(self, position: float) -> None:
        """Seek the media to a specific location."""
        await self.speaker.seek(position)
        self.async_write_ha_state()

    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play media using Chromecast functionality."""
        # Handle media_source
        if media_source.is_media_source_id(media_id):
            play_item = await media_source.async_resolve_media(
                self.hass, media_id, self.entity_id
            )
            media_id = play_item.url

        # Process the media URL for local serving if needed
        media_id = async_process_play_media_url(self.hass, media_id)

        _LOGGER.info(
            "Playing media via Chromecast: type=%s, url=%s", media_type, media_id
        )

        try:
            # Check if Chromecast device is available
            if self._chromecast_device is None or self._media_controller is None:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="chromecast_not_available",
                    translation_placeholders={"speaker_ip": str(self._speaker_ip)},
                )

            idle_tries = 0
            while(self._chromecast_device.is_idle and idle_tries < 5):
                await asyncio.sleep(1)
                idle_tries += 1
                
            if self._chromecast_device.is_idle:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="chromecast_not_available",
                    translation_placeholders={"speaker_ip": str(self._speaker_ip)},
                )

            content_type = self._get_content_type(media_type, media_id)
            await self.hass.async_add_executor_job(
                self._media_controller.play_media, media_id, content_type
            )

            self._attr_media_title = (
                media_id.split("/")[-1] if "/" in media_id else media_id
            )
            self._attr_source = "Chromecast built-in"
            self._attr_state = MediaPlayerState.PLAYING
            self.async_write_ha_state()

            _LOGGER.info("Successfully started Chromecast playback for %s", media_id)

        except Exception as err:
            _LOGGER.error("Failed to play media via Chromecast: %s", err)
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="media_playback_failed",
                translation_placeholders={
                    "media_id": media_id,
                    "error": str(err),
                },
            ) from err

    async def _async_setup_chromecast(self, secondTry = False) -> None:
        """Set up Chromecast device for media playback."""
        if self._speaker_ip is None:
            _LOGGER.warning("No speaker IP available for Chromecast setup")
            return

        try:
            _LOGGER.debug("Discovering Chromecast on %s", self._speaker_ip)

            # Get Home Assistant's shared Zeroconf instance
            zc = await zeroconf.async_get_instance(self.hass)

            # Create a simple cast listener to handle discovered devices
            def cast_listener(uuid, service):
                """Handle discovered cast device."""
                if uuid in browser.devices:
                    device = browser.devices[uuid]
                    if device.host == self._speaker_ip:
                        _LOGGER.debug("Found matching Chromecast device: %s", device.friendly_name)

            # Create browser and start discovery using shared Zeroconf instance
            browser = await self.hass.async_add_executor_job(
                CastBrowser,
                SimpleCastListener(cast_listener),
                zc
            )
            
            await self.hass.async_add_executor_job(browser.start_discovery)
            
            # Wait a bit for discovery to find devices
            await asyncio.sleep(3)

            # Look for a Chromecast device on the same IP as our Bose speaker
            chromecast_found = False
            for uuid, device in browser.devices.items():
                if device.host == self._speaker_ip:
                    # Create chromecast instance
                    self._chromecast_device = await self.hass.async_add_executor_job(
                        pychromecast.get_chromecast_from_cast_info,
                        device,
                        zc
                    )
                    self._media_controller = self._chromecast_device.media_controller
                    _LOGGER.info(
                        "Found Chromecast device at %s: %s",
                        self._speaker_ip,
                        device.friendly_name,
                    )
                    chromecast_found = True
                    break

            if self._chromecast_device:
                await self.hass.async_add_executor_job(self._chromecast_device.wait)
                _LOGGER.debug("Chromecast device connected successfully")
            elif not chromecast_found:
                _LOGGER.debug("Chromecast device not found for Bose speaker at %s", self._speaker_ip)
                if not secondTry:
                    await self.speaker.set_chromecast(True)
                    # Stop discovery before retrying
                    await self.hass.async_add_executor_job(discovery.stop_discovery, browser)
                    await self._async_setup_chromecast(True)
                    return
                else:
                    _LOGGER.warning("No Chromecast device found for Bose speaker after enabling Chromecast")
                
            # Stop discovery
            await self.hass.async_add_executor_job(discovery.stop_discovery, browser)

        except (ConnectionError, TimeoutError, OSError, AttributeError) as err:
            _LOGGER.error("Error setting up Chromecast: %s", err)

    def _get_content_type(self, media_type: MediaType | str, media_url: str) -> str:
        """Determine the appropriate content type for Chromecast."""
        # If media_type is already specific, use it
        if isinstance(media_type, str) and "/" in media_type:
            return media_type

        # Determine content type from URL extension or media_type
        media_url_lower = media_url.lower()

        if media_type == MediaType.MUSIC or any(
            media_url_lower.endswith(ext)
            for ext in [".mp3", ".wav", ".flac", ".m4a", ".aac"]
        ):
            return "audio/mpeg"

        if media_type == MediaType.VIDEO or any(
            media_url_lower.endswith(ext) for ext in [".mp4", ".avi", ".mkv", ".webm"]
        ):
            return "video/mp4"

        if media_url_lower.endswith(".m3u8"):
            return "application/x-mpegURL"

        if media_url_lower.endswith(".pls"):
            return "audio/x-scpls"

        # Default to audio for unknown types
        return "audio/mpeg"

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Implement the websocket media browsing helper."""
        return await media_source.async_browse_media(
            self.hass,
            media_content_id,
            # Filter to only show audio content that the speaker can likely play
            content_filter=lambda item: (
                item.media_content_type.startswith("audio/")
                or item.media_content_type == MediaType.MUSIC
                or item.media_class in {"music", "podcast", "audiobook"}
            ),
        )

    async def async_join_players(self, group_members: list[str]) -> None:
        """Join `group_members` as a player group with the current player."""
        registry = er.async_get(self.hass)
        entities = [registry.async_get(entity_id) for entity_id in group_members]

        guids = [
            self.hass.data[DOMAIN][entity.config_entry_id]
            .get("system_info", {})
            .get("guid", None)
            for entity in entities
        ]

        if self._active_group_id is not None:
            master_id = (
                self._attr_group_members[0] if self._attr_group_members else None
            )

            if master_id is not None and master_id != self.entity_id:
                _LOGGER.warning(
                    "Speakers can only join the master of the group, which is %s",
                    master_id,
                )
                _LOGGER.warning("Running action on master speaker")
                master: BoseSpeaker = self.hass.data[DOMAIN][
                    registry.async_get(master_id).config_entry_id
                ]["speaker"]
                await master.add_to_active_group(self._active_group_id, guids)
                return

            await self.speaker.add_to_active_group(self._active_group_id, guids)
        else:
            await self.speaker.set_active_group(guids)
        self.async_write_ha_state()

    async def async_unjoin_player(self) -> None:
        """Unjoin the player from a group."""

        if not self._attr_group_members:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="not_in_group",
                translation_placeholders={"entity_id": self.entity_id},
            )

        master_entity_id = self._attr_group_members[0]

        if self.entity_id == master_entity_id:
            await self.speaker.stop_active_groups()
        else:
            master_entity = er.async_get(self.hass).async_get(master_entity_id)
            if master_entity is None:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="master_not_found",
                    translation_placeholders={"entity_id": master_entity_id},
                )
            master_speaker = self.hass.data[DOMAIN][master_entity.config_entry_id][
                "speaker"
            ]
            await master_speaker.remove_from_active_group(
                self._active_group_id, [self._device_id]
            )

    @property
    def source_list(self) -> list[str] | None: # pyright: ignore[reportIncompatibleVariableOverride]
        """Return the list of available input sources."""
        
        if(self._attr_source == "Chromecast built-in"):
            return ["Chromecast built-in"] + self._attr_source_list
        
        return self._attr_source_list

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:  # pyright: ignore[reportIncompatibleVariableOverride]
        """Return the features supported by this media player."""
        now = self._now_playing_result or {}

        def _can(key: str) -> bool:
            if isinstance(now, dict):
                state = now.get("state") or {}
                return bool(state.get(key, False))

            state = getattr(now, "state", None)
            if isinstance(state, dict):
                return bool(state.get(key, False))

            get_fn = getattr(now, "get", None)
            if callable(get_fn):
                try:
                    state = get_fn("state", {})
                except (AttributeError, TypeError):
                    return False
                if isinstance(state, dict):
                    return bool(state.get(key, False))
                return False

            return bool(getattr(state, key, False))

        if not now:
            return MediaPlayerEntityFeature.PLAY

        return (
            MediaPlayerEntityFeature.TURN_OFF
            | MediaPlayerEntityFeature.TURN_ON
            | (MediaPlayerEntityFeature.NEXT_TRACK if _can("canSkipNext") else 0)
            | (MediaPlayerEntityFeature.PAUSE if _can("canPause") else 0)
            | MediaPlayerEntityFeature.PLAY
            | (
                MediaPlayerEntityFeature.PREVIOUS_TRACK
                if _can("canSkipPrevious")
                else 0
            )
            | (MediaPlayerEntityFeature.SEEK if _can("canSeek") else 0)
            | MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_STEP
            | MediaPlayerEntityFeature.VOLUME_MUTE
            | (MediaPlayerEntityFeature.STOP if _can("canStop") else 0)
            | MediaPlayerEntityFeature.GROUPING
            | MediaPlayerEntityFeature.SELECT_SOURCE
            | ((MediaPlayerEntityFeature.PLAY_MEDIA | MediaPlayerEntityFeature.BROWSE_MEDIA) if self._chromecast_device is not None else 0)
        )
