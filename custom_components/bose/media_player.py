"""Support for Bose media player."""

import logging

from pybose.BoseResponse import AudioVolume, ContentNowPlaying, SystemInfo
from pybose.BoseSpeaker import BoseSpeaker

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
import homeassistant.helpers.entity_registry as er
from homeassistant.util import dt

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Bose media player."""
    speaker = hass.data[DOMAIN][config_entry.entry_id]["speaker"]
    system_info = hass.data[DOMAIN][config_entry.entry_id]["system_info"]

    async_add_entities([BoseMediaPlayer(speaker, system_info)], update_before_add=False)


class BoseMediaPlayer(MediaPlayerEntity):
    """Representation of a Bose speaker as a media player."""

    def __init__(
        self,
        speaker: BoseSpeaker,
        system_info: SystemInfo,
    ) -> None:
        """Initialize the Bose media player."""
        self.speaker = speaker
        self._name = system_info["name"]
        self._device_id = speaker.get_device_id()
        self._is_on = False
        self._state = MediaPlayerState.OFF
        self._volume_level = 0.5
        self._muted = False
        self._source = None
        self._album_art = None
        self._media_title = None
        self._media_artist = None
        self._media_album_name = None
        self._media_duration = None
        self._media_position = None
        self._last_update = None
        self._now_playing_result = None
        self._group_members = []
        self._active_group_id = None

        speaker.attach_receiver(self.parse_message)

    def parse_message(self, data):
        """Parse the message from the speaker."""

        resource = data.get("header", {}).get("resource")
        body = data.get("body", {})
        if resource == "/audio/volume":
            self._parse_audio_volume(AudioVolume(body))
        elif resource == "/system/power/control":
            self._is_on = body.get("power") == "ON"
            self._state = MediaPlayerState.OFF if not self._is_on else self._state
        elif resource == "/content/nowPlaying":
            self._parse_now_playing(ContentNowPlaying(body))
        elif resource == "/grouping/activeGroups":
            self._parse_grouping(body)

        self.async_write_ha_state()

    def _parse_grouping(self, data: dict):
        active_groups = data.get("activeGroups", {})

        if len(active_groups) == 0:
            self._group_members = []
            self._active_group_id = None
            return

        active_group = active_groups[0]

        guids = [
            product.get("productId", None) for product in active_group.get("products")
        ]

        if len(guids) == 0:
            self._group_members = []
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

        self._group_members = entity_ids
        self._active_group_id = active_group.get("activeGroupId")

    def _parse_audio_volume(self, data: AudioVolume):
        self._volume_level = data.get("value", 0) / 100
        # TODO: Mute is implemented in another way?
        self._muted = self._volume_level == 0

    def _parse_now_playing(self, data: ContentNowPlaying):
        try:
            match data.get("state", {}).get("status"):
                case "PLAY":
                    self._state = MediaPlayerState.PLAYING
                case "PAUSED":
                    self._state = MediaPlayerState.PAUSED
                case "BUFFERING":
                    self._state = MediaPlayerState.BUFFERING
                case "STOPPED":
                    self._state = MediaPlayerState.IDLE
                case None:
                    self._state = MediaPlayerState.OFF
                case _:
                    logging.warning(
                        "State not implemented: %s", data.get("state", {}).get("status")
                    )
                    self._state = MediaPlayerState.ON
        except AttributeError:
            self._state = MediaPlayerState.ON

        self._source = data.get("source", {}).get("sourceDisplayName", None)

        self._media_title = data.get("metadata", {}).get("trackName")
        self._media_artist = data.get("metadata", {}).get("artist")
        self._media_album_name = data.get("metadata", {}).get("album")
        self._media_duration = int(data.get("metadata", {}).get("duration", 999))
        self._media_position = int(data.get("state", {}).get("timeIntoTrack", 0))
        self._last_update = dt.utcnow()

        self._now_playing_result: ContentNowPlaying = data

        if (
            data.get("container", {}).get("contentItem", {}).get("source") == "PRODUCT"
            and data.get("container", {}).get("contentItem", {}).get("sourceAccount")
            == "TV"
        ):
            self._source = "TV"
            self._media_title = "TV"
            self._media_album_name = None
            self._media_artist = None
            self._media_duration = None
            self._media_position = None

        self._album_art = (
            data.get("track", {}).get("contentItem", {}).get("containerArt")
        )

    async def async_update(self) -> None:
        """Fetch new state data from the speaker."""
        data = await self.speaker.get_now_playing()
        self._parse_now_playing(data)

        data = await self.speaker.get_audio_volume()
        self._parse_audio_volume(data)

        active_groups = await self.speaker.get_active_groups()
        self._parse_grouping({"activeGroups": active_groups})
        self.async_write_ha_state()

    async def async_turn_on(self) -> None:
        """Turn on the speaker."""
        await self.speaker.set_power_state(True)
        self._is_on = True
        self._state = MediaPlayerState.IDLE
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        """Turn off the speaker."""
        await self.speaker.set_power_state(False)
        self._is_on = False
        self._state = MediaPlayerState.OFF
        self.async_write_ha_state()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level (0.0 to 1.0)."""
        await self.speaker.set_audio_volume(int(volume * 100))
        self._volume_level = volume
        self.async_write_ha_state()

    async def async_media_play(self) -> None:
        """Play the current media."""
        await self.speaker.play()
        self._state = MediaPlayerState.PLAYING
        self.async_write_ha_state()

    async def async_media_pause(self) -> None:
        """Pause the current media."""
        await self.speaker.pause()
        self._state = MediaPlayerState.PAUSED
        self.async_write_ha_state()

    async def async_media_next_track(self) -> None:
        """Skip to the next track."""
        await self.speaker.skip_next()
        self.async_write_ha_state()

    async def async_media_previous_track(self) -> None:
        """Skip to the previous track."""
        await self.speaker.skip_previous()
        self.async_write_ha_state()

    async def async_media_seek(self, position):
        """Seek the media to a specific location."""
        await self.speaker.seek(position)
        self.async_write_ha_state()

    async def async_join_players(self, group_members):
        """Join `group_members` as a player group with the current player."""
        registry = er.async_get(self.hass)
        entities = [registry.async_get(entity_id) for entity_id in group_members]

        guids = [
            self.hass.data[DOMAIN][entity.config_entry_id]
            .get("system_info", {})
            .get("guid", None)
            for entity in entities
        ]

        if not self._group_members[0] == self.entity_id:
            logging.warning(
                "Speakers can only join the master of the group, which is %s",
                self._group_members[0],
            )
            logging.warning("Running action on master speaker.")
            master: BoseSpeaker = self.hass.data[DOMAIN][
                registry.async_get(self._group_members[0]).config_entry_id
            ]["speaker"]
            await master.add_to_active_group(self._active_group_id, guids)
            return

        if self._active_group_id is not None:
            await self.speaker.add_to_active_group(self._active_group_id, guids)
        else:
            await self.speaker.set_active_group(guids)
        self.async_write_ha_state()

    async def async_unjoin_player(self):
        """Unjoin the player from a group."""

        master_entity_id = self._group_members[0]

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
    def name(self) -> str:
        """Return the name of the speaker."""
        return self._name

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the current state of the player."""
        return self._state

    @property
    def volume_level(self) -> float:
        """Return the volume level (0.0 to 1.0)."""
        return self._volume_level

    @property
    def is_volume_muted(self) -> bool:
        """Return True if volume is muted."""
        return self._muted

    @property
    def media_title(self) -> str:
        """Return the title of current playing media."""
        return self._media_title

    @property
    def media_artist(self) -> str:
        """Return the artist of current playing media (Music track only)."""
        return self._media_artist

    @property
    def media_album_name(self) -> str:
        """Return the album of current playing media (Music track only)."""
        return self._media_album_name

    @property
    def media_duration(self) -> int:
        """Return the duration of current playing media in seconds."""
        return self._media_duration

    @property
    def media_position(self) -> int:
        """Return the position of current playing media in seconds."""
        return self._media_position

    @property
    def media_position_updated_at(self):
        """Return the last time the media position was updated."""
        return self._last_update

    @property
    def media_image_url(self) -> str:
        """Return the URL of the album art."""
        return self._album_art

    @property
    def source(self) -> str:
        """Return the current input source."""
        return self._source

    @property
    def unique_id(self) -> str:
        """Return a unique ID for this entity."""
        return f"{self._device_id}-media"

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Return the features supported by this media player."""
        if self._now_playing_result is None:
            return MediaPlayerEntityFeature.PLAY
        return (
            MediaPlayerEntityFeature.TURN_OFF
            | MediaPlayerEntityFeature.TURN_ON
            | (
                MediaPlayerEntityFeature.NEXT_TRACK
                if self._now_playing_result.get("state", {}).get("canSkipNext", False)
                else 0
            )
            | (
                MediaPlayerEntityFeature.PAUSE
                if self._now_playing_result.get("state", {}).get("canPause", False)
                else 0
            )
            | MediaPlayerEntityFeature.PLAY
            | (
                MediaPlayerEntityFeature.PREVIOUS_TRACK
                if self._now_playing_result.get("state", {}).get(
                    "canSkipPrevious", False
                )
                else 0
            )
            | (
                MediaPlayerEntityFeature.SEEK
                if self._now_playing_result.get("state", {}).get("canSeek", False)
                else 0
            )
            | MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_STEP
            | (
                MediaPlayerEntityFeature.STOP
                if self._now_playing_result.get("state", {}).get("canStop", False)
                else 0
            )
            | MediaPlayerEntityFeature.GROUPING
        )

    @property
    def group_members(self):
        """Return the list of members of this player's group."""
        return self._group_members

    @property
    def device_info(self) -> dict | None:
        """Return device information for Home Assistant integration."""
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "manufacturer": "Bose",
            "name": self._name,
        }
