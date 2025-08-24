"""Support for Bose media player."""

from pybose.BoseResponse import (
    AudioVolume,
    BluetoothSinkList,
    BluetoothSinkStatus,
    BluetoothSourceStatus,
    ContentNowPlaying,
    SystemInfo,
)
from pybose.BoseSpeaker import BoseSpeaker

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
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
        self._attr_muted = False
        self._attr_source = None
        self._attr_media_image_url = None
        self._attr_media_title = None
        self._attr_media_artist = None
        self._attr_media_album_name = None
        self._attr_media_duration = None
        self._attr_media_position = None
        self._attr_media_position_updated_at = None
        self._now_playing_result = None  # type: ignore
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

        speaker.attach_receiver(self.parse_message)

        hass.async_create_task(self.async_update())

    def parse_message(self, data):
        """Parse the message from the speaker."""

        resource = data.get("header", {}).get("resource")
        body = data.get("body", {})
        if resource == "/audio/volume":
            self._parse_audio_volume(AudioVolume(body))
        elif resource == "/system/power/control":
            self._is_on = body.get("power") == "ON"
            self._attr_state = (
                MediaPlayerState.OFF if not self._is_on else self._attr_state
            )
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

        registry = er.async_get(self.hass)

        entity_ids = [
            registry.async_get_entity_id(
                "media_player",
                DOMAIN,
                f"{guid}-media",
            )
            for guid in guids
        ]

        self._attr_group_members = entity_ids
        self._active_group_id = active_group.get("activeGroupId")

    def _parse_audio_volume(self, data: AudioVolume):
        self._attr_volume_level = data.get("value", 0) / 100
        self._attr_muted = data.get("muted")

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
                case "STOPPED":
                    self._attr_state = MediaPlayerState.IDLE
                case None:
                    self._attr_state = MediaPlayerState.STANDBY
                case _:
                    _LOGGER.warning("State not implemented: %s", status)
                    self._attr_state = MediaPlayerState.ON
        except AttributeError:
            self._attr_state = MediaPlayerState.ON

        self._attr_source = data.get("source", {}).get("sourceDisplayName", None)

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
        self._attr_source_list = [
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
        if isinstance(status, dict):
            active_device = status.get("activeDevice")
        else:
            get_fn = getattr(status, "get", None)
            if callable(get_fn):
                try:
                    active_device = get_fn("activeDevice")
                except Exception:
                    active_device = None

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
        result = await self.speaker.set_source(
            source_data.get("source"), source_data.get("sourceAccount")
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
        self._attr_muted = mute
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
            if self._attr_group_members[0] != self.entity_id:
                _LOGGER.warning(
                    "Speakers can only join the master of the group, which is %s",
                    self._attr_group_members[0],
                )
                _LOGGER.warning("Running action on master speaker")
                master: BoseSpeaker = self.hass.data[DOMAIN][
                    registry.async_get(self._attr_group_members[0]).config_entry_id
                ]["speaker"]
                await master.add_to_active_group(self._active_group_id, guids)
                return

            await self.speaker.add_to_active_group(self._active_group_id, guids)
        else:
            await self.speaker.set_active_group(guids)
        self.async_write_ha_state()

    async def async_unjoin_player(self) -> None:
        """Unjoin the player from a group."""

        master_entity_id = self._attr_group_members[0]

        if self.entity_id == master_entity_id:
            await self.speaker.stop_active_groups()
        else:
            master_entity = er.async_get(self.hass).async_get(master_entity_id)
            master_speaker = self.hass.data[DOMAIN][master_entity.config_entry_id][
                "speaker"
            ]
            await master_speaker.remove_from_active_group(
                self._active_group_id, [self._device_id]
            )

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
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
        )
