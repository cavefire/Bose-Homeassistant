"""Support for Bose media player."""

import logging

from pybose.BoseResponse import AudioVolume, ContentNowPlaying
from pybose.BoseSpeaker import BoseSpeaker

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bose media player."""
    speaker = hass.data[DOMAIN][config_entry.entry_id]["speaker"]
    system_info = hass.data[DOMAIN][config_entry.entry_id]["system_info"]

    async_add_entities([BoseMediaPlayer(speaker, system_info)], update_before_add=True)


class BoseMediaPlayer(MediaPlayerEntity):
    """Representation of a Bose speaker as a media player."""

    def __init__(self, speaker: BoseSpeaker, system_info) -> None:
        """Initialize the Bose media player."""
        self.speaker = speaker
        self._name = system_info.name
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

        speaker.attach_receiver(self.parse_message)

    def parse_message(self, data):
        """Parse the message from the speaker."""

        resource = data.get("header", {}).get("resource")
        body = data.get("body", {})
        logging.info("Received message: %s", resource)
        if resource == "/audio/volume":
            self._parse_audio_volume(AudioVolume(body))
        elif resource == "/system/power/control":
            self._is_on = body.get("power") == "ON"
            self._state = MediaPlayerState.OFF if not self._is_on else self._state
        elif resource == "/content/nowPlaying":
            self._parse_now_playing(ContentNowPlaying(body))

        self.async_write_ha_state()

    def _parse_audio_volume(self, data: AudioVolume):
        self._volume_level = data.value / 100
        # TODO: Mute is implemented in another way?
        self._muted = self.volume_level == 0

    def _parse_now_playing(self, data: ContentNowPlaying):
        try:
            match data.state.status:
                case "PLAY":
                    self._state = MediaPlayerState.PLAYING
                case "PAUSED":
                    self._state = MediaPlayerState.PAUSED
                case "BUFFERING":
                    self._state = MediaPlayerState.BUFFERING
                case "STOPPED":
                    self._state = MediaPlayerState.IDLE
                case _:
                    logging.warning("State not implemented: %s", data.state.status)
                    self._state = MediaPlayerState.ON
        except AttributeError:
            self._state = MediaPlayerState.ON

        self._source = data.source.sourceDisplayName if data.source else None

        try:
            self._media_title = (
                data.metadata.trackName
                if data.metadata.trackName
                else self._media_title
            )
            self._media_artist = (
                data.metadata.artist if data.metadata.artist else self._media_artist
            )
            self._media_album_name = (
                data.metadata.album if data.metadata.album else self._media_album_name
            )
            self._media_duration = (
                data.metadata.duration
                if data.metadata.duration
                else self._media_duration
            )
            self._media_position = (
                data.state.timeIntoTrack
                if data.state.timeIntoTrack
                else self._media_position
            )
        except AttributeError:
            if self._state not in (
                MediaPlayerState.PAUSED,
                MediaPlayerState.BUFFERING,
            ):
                self._media_title = None
                self._media_artist = None
                self._media_album_name = None
                self._media_duration = None
                self._media_position = None

        try:
            if (
                data.container.contentItem.source == "PRODUCT"
                and data.container.contentItem.sourceAccount == "TV"
            ):
                self._source = "TV"
                self._media_title = "TV"
                self._media_album_name = None
                self._media_artist = None
                self._media_duration = None
                self._media_position = None
        except AttributeError:
            pass

        try:
            self._album_art = (
                data.track.contentItem.containerArt
                if data.track.contentItem
                else self._album_art
            )
        except AttributeError:
            if self._state not in (
                MediaPlayerState.PAUSED,
                MediaPlayerState.BUFFERING,
            ):
                self._album_art = None

    async def async_update(self) -> None:
        """Fetch new state data from the speaker."""
        data = await self.speaker.get_now_playing()
        self._parse_now_playing(data)

        data = await self.speaker.get_audio_volume()
        self._parse_audio_volume(data)

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
        return (
            MediaPlayerEntityFeature.TURN_ON
            | MediaPlayerEntityFeature.TURN_OFF
            | MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.PAUSE
            | MediaPlayerEntityFeature.PLAY
            | MediaPlayerEntityFeature.NEXT_TRACK
            | MediaPlayerEntityFeature.PREVIOUS_TRACK
        )

    @property
    def device_info(self) -> dict | None:
        """Return device information for Home Assistant integration."""
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "manufacturer": "Bose",
            "name": self._name,
        }
