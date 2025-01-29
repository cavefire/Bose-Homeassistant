"""Support for Bose media player."""

from pybose.BoseResponse import ContentNowPlaying
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

    # Fetch system info
    system_info = await speaker.get_system_info()

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
        self._track_info = None
        self._source = None
        self._album_art = None

        speaker.attach_receiver(self.parse_message)

    def parse_message(self, data):
        """Parse the message from the speaker."""

        resource = data.get("header", {}).get("resource")
        body = data.get("body", {})
        if resource == "/audio/volume":
            self._volume_level = body.get("value", 0) / 100
            self._muted = self.volume_level == 0
        elif resource == "/system/power/control":
            self._is_on = body.get("power") == "ON"
            self._state = MediaPlayerState.OFF if not self._is_on else self._state
        elif resource == "/content/nowPlaying":
            data = ContentNowPlaying(body)
            if data.metadata:
                self._track_info = f"{data.metadata.artist} - {data.metadata.trackName}"
                self._album_art = data.track.contentItem.containerArt
                self._source = data.source.sourceDisplayName

                self._state = (
                    MediaPlayerState.PAUSED
                    if data.state.status == "PAUSED"
                    else MediaPlayerState.PLAYING
                )
            else:
                self._track_info = None
                self._album_art = None
                self._source = None
                self._state = MediaPlayerState.ON

    async def async_update(self) -> None:
        """Fetch new state data from the speaker."""
        try:
            # Get power state
            power_state = await self.speaker.get_power_state()
            self._is_on = power_state.get("power") == "ON"

            if not self._is_on:
                self._state = MediaPlayerState.OFF
                return

            # Get volume
            volume_info = await self.speaker.get_audio_volume()
            self._volume_level = volume_info.value / 100
            self._muted = volume_info.muted

            # Get track info
            track_info = await self.speaker.get_now_playing()
            if track_info.metadata:
                self._track_info = (
                    f"{track_info.metadata.artist} - {track_info.metadata.trackName}"
                )
                self._album_art = track_info.track.contentItem.containerArt
                self._source = track_info.source.sourceDisplayName

                self._state = (
                    MediaPlayerState.PAUSED
                    if track_info.state.status == "PAUSED"
                    else MediaPlayerState.PLAYING
                )

            else:
                self._track_info = None
                self._album_art = None
                self._source = None
                self._state = MediaPlayerState.ON

        except Exception:  # noqa: BLE001
            self._state = MediaPlayerState.OFF
            self._is_on = False

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
        return self._track_info

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
