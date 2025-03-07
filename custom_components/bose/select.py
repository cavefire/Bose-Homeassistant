"""Support for Bose source selection."""

import logging

from pybose.BoseResponse import (
    AudioMode,
    ContentNowPlaying,
    DualMonoSettings,
    RebroadcastLatencyMode,
    Sources,
)
from pybose.BoseSpeaker import BoseSpeaker

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN

HUMINZED_OPTIONS = {
    "DYNAMIC_DIALOG": "AI Dialogue Mode",
    "DIALOG": "Dialogue Mode",
    "NORMAL": "Normal Mode",
    "LEFT": "Track 1",
    "RIGHT": "Track 2",
    "BOTH": "Both",
    "SYNC_TO_ROOM": "Sync With TV",
    "SYNC_TO_ZONE": "Sync With Group",
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Bose select entity."""
    speaker = hass.data[DOMAIN][config_entry.entry_id]["speaker"]
    system_info = hass.data[DOMAIN][config_entry.entry_id]["system_info"]

    entities = []

    # Fetch sources
    try:
        sources = await speaker.get_sources()
        entities.append(BoseSourceSelect(speaker, system_info, config_entry, sources))
    except Exception as e:
        logging.warning(f"Failed to fetch sources: {e}")

    try:
        audio_mode = await speaker.get_audio_mode()
        entities.append(BoseAudioSelect(speaker, system_info, config_entry, audio_mode))
    except Exception as e:
        if e.args[1] == 0:
            logging.debug(f"Speaker does not support audio mode")
        else:
            logging.error(f"Failed to fetch audio mode: {e}")

    try:
        dual_mono_setting = await speaker.get_dual_mono_setting()
        entities.append(
            BoseDualMonoSelect(speaker, system_info, config_entry, dual_mono_setting)
        )
    except Exception as e:
        if e.args[1] == 0:
            logging.debug(f"Speaker does not support dual mono settings")
        else:
            logging.error(f"Failed to fetch dual mono settings: {e}")

    try:
        rebroadcast_latency_mode = await speaker.get_rebroadcast_latency_mode()
        entities.append(
            BoseRebroadcastLatencyModeSelect(
                speaker, system_info, config_entry, rebroadcast_latency_mode
            )
        )
    except Exception as e:
        if e.args[1] == 0:
            logging.debug(f"Speaker does not support rebroadcast latency mode")
        else:
            logging.error(f"Failed to fetch rebroadcast latency mode: {e}")

    async_add_entities(entities, update_before_add=False)


class BoseSourceSelect(SelectEntity):
    """Representation of a Bose device source selector."""

    def __init__(
        self, speaker: BoseSpeaker, speaker_info, config_entry, sources: Sources
    ) -> None:
        """Initialize the select entity."""
        self.speaker = speaker
        self._attr_name = f"{speaker_info['name']} Source"
        self._attr_unique_id = f"{config_entry.data['guid']}_source_select"
        self.speaker_info = speaker_info
        self.config_entry = config_entry

        self._available_sources = {
            "Optical": {"source": "PRODUCT", "sourceAccount": "AUX_DIGITAL"},
            "Cinch": {"source": "PRODUCT", "sourceAccount": "AUX_ANALOG"},
            "TV": {"source": "PRODUCT", "sourceAccount": "TV"},
        }

        self._attr_options = []
        for source in sources.get("sources", []):
            if (
                (source.get("status", None) in ("AVAILABLE", "NOT_CONFIGURED"))
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
                    self._available_sources[
                        f"{source.get('sourceName', None).capitalize()}: {source.get('sourceAccountName', None)}"
                    ] = {
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
                        self._attr_options.append(key)

        self._selected_source = None

        self.speaker.attach_receiver(self._parse_message)

    async def async_select_option(self, option: str) -> None:
        """Change the source on the speaker."""
        if option in self._available_sources:
            source_data = self._available_sources[option]
            self._parse_now_playing(
                await self.speaker.set_source(
                    source_data["source"], source_data["sourceAccount"]
                )
            )

    def _parse_message(self, data):
        """Parse real-time messages from the speaker."""
        if data.get("header", {}).get("resource") == "/content/nowPlaying":
            self._parse_now_playing(ContentNowPlaying(data.get("body")))

    def _parse_now_playing(self, data: ContentNowPlaying):
        """Update the selected source based on now playing data."""
        for source_name, source_data in self._available_sources.items():
            if (
                data.get("container", {}).get("contentItem", {}).get("source")
                == source_data["source"]
            ):
                if source_data["source"] in ("SPOTIFY", "AMAZON", "DEEZER"):
                    if (
                        data.get("container", {})
                        .get("contentItem", {})
                        .get("sourceAccount")
                        != source_data["accountId"]
                    ):
                        continue
                elif source_data["sourceAccount"] != data.get("container", {}).get(
                    "contentItem", {}
                ).get("sourceAccount"):
                    continue

                self._selected_source = source_name
                self.async_write_ha_state()
                return

        self._selected_source = (
            data.get("container", {}).get("contentItem", {}).get("source").capitalize()
        )
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Fetch the current playing source."""
        now_playing = await self.speaker.get_now_playing()
        self._parse_now_playing(now_playing)

    @property
    def current_option(self) -> str | None:
        """Return the currently selected option."""
        return self._selected_source

    @property
    def unique_id(self) -> str:
        """Return a unique ID for this entity."""
        return self._attr_unique_id

    @property
    def device_info(self):
        """Return device information about this entity."""
        return {
            "identifiers": {(DOMAIN, self.config_entry.data["guid"])},
        }


class BoseBaseSelect(SelectEntity):
    """Base class for Bose device selectors."""

    def __init__(
        self,
        speaker: BoseSpeaker,
        speaker_info,
        config_entry,
        mode_data,
        mode_type,
        name_suffix,
        unique_id_suffix,
    ) -> None:
        """Initialize the select entity."""
        self.speaker = speaker
        self.speaker_info = speaker_info
        self.config_entry = config_entry

        self._attr_name = f"{speaker_info['name']} {name_suffix}"
        self._attr_unique_id = f"{config_entry.data['guid']}_{unique_id_suffix}"
        self._attr_options = []
        self._selected_audio = None
        self._attr_entity_category = EntityCategory.CONFIG

        self.speaker.attach_receiver(self._parse_message)
        self._parse_audio_mode(mode_data, mode_type)

    async def async_select_option(self, option: str) -> None:
        """Change the audio mode on the speaker."""
        await getattr(self.speaker, self._set_method)(option)

    def _parse_audio_mode(self, data, mode_type):
        self._selected_audio = data.get(self._value_key)
        self._attr_options = [
            HUMINZED_OPTIONS.get(option, option)
            for option in data.get("properties", {}).get(self._supported_key, [])
        ]
        if self.hass:
            self.async_write_ha_state()

    def _parse_message(self, data):
        """Parse real-time messages from the speaker."""
        if data.get("header", {}).get("resource") == self._resource_path:
            self._parse_audio_mode(self._mode_class(data.get("body")), self._mode_class)

    @property
    def current_option(self) -> str | None:
        """Return the currently selected option."""
        if HUMINZED_OPTIONS.get(self._selected_audio):
            return HUMINZED_OPTIONS.get(self._selected_audio)
        return self._selected_audio

    @property
    def unique_id(self) -> str:
        """Return a unique ID for this entity."""
        return self._attr_unique_id

    @property
    def device_info(self):
        """Return device information about this entity."""
        return {"identifiers": {(DOMAIN, self.config_entry.data["guid"])}}


class BoseAudioSelect(BoseBaseSelect):
    """Representation of a Bose device audio selector."""

    _set_method = "set_audio_mode"
    _value_key = "value"
    _supported_key = "supportedValues"
    _resource_path = "/audio/mode"
    _mode_class = AudioMode

    def __init__(self, speaker, speaker_info, config_entry, audioMode):
        super().__init__(
            speaker,
            speaker_info,
            config_entry,
            audioMode,
            AudioMode,
            "Audio",
            "audio_select",
        )


class BoseDualMonoSelect(BoseBaseSelect):
    """Representation of a Bose device dual mono selector."""

    _set_method = "set_dual_mono_setting"
    _value_key = "value"
    _supported_key = "supportedValues"
    _resource_path = "/audio/dualMonoSelect"
    _mode_class = DualMonoSettings

    def __init__(self, speaker, speaker_info, config_entry, audioMode):
        super().__init__(
            speaker,
            speaker_info,
            config_entry,
            audioMode,
            DualMonoSettings,
            "Dual Mono",
            "dual_mono_select",
        )


class BoseRebroadcastLatencyModeSelect(BoseBaseSelect):
    """Representation of a Bose device rebroadcast latency mode selector."""

    _set_method = "set_rebroadcast_latency_mode"
    _value_key = "mode"
    _supported_key = "supportedModes"
    _resource_path = "/audio/rebroadcastLatency/mode"
    _mode_class = RebroadcastLatencyMode

    def __init__(self, speaker, speaker_info, config_entry, audioMode):
        super().__init__(
            speaker,
            speaker_info,
            config_entry,
            audioMode,
            RebroadcastLatencyMode,
            "Rebroadcast Latency Mode",
            "rebroadcast_latency_mode_select",
        )
