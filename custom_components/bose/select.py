"""Support for Bose source selection."""

from pybose.BoseResponse import (
    AudioMode,
    CecSettings,
    ContentNowPlaying,
    DualMonoSettings,
    RebroadcastLatencyMode,
)
from pybose.BoseSpeaker import BoseSpeaker

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import BoseBaseEntity

HUMINZED_OPTIONS = {
    # Audio Mode
    "DYNAMIC_DIALOG": "dynamic_dialog",
    "DIALOG": "dialog",
    "NORMAL": "normal",
    # Dual Mono
    "LEFT": "track1",
    "RIGHT": "track2",
    "BOTH": "both",
    # Rebroadcast Latency
    "SYNC_TO_ROOM": "sync_to_room",
    "SYNC_TO_ZONE": "sync_with_group",
    # CEC
    "ON": "cec_active",
    "OFF": "cec_inactive",
    "ALTERNATE_ON": "option2",
    "ALTMODE_3": "option3",
    "ALTMODE_4": "option4",
    "ALTMODE_5": "option5",
    "ALTMODE_6": "option6",
    "ALTMODE_7": "option7",
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Bose select entity."""
    speaker: BoseSpeaker = hass.data[DOMAIN][config_entry.entry_id]["speaker"]
    system_info = hass.data[DOMAIN][config_entry.entry_id]["system_info"]

    entities = []

    if speaker.has_capability("/audio/mode"):
        entities.append(BoseAudioSelect(speaker, system_info, config_entry, hass))

    if speaker.has_capability("/audio/dualMonoSelect"):
        entities.append(BoseDualMonoSelect(speaker, system_info, config_entry, hass))

    if speaker.has_capability("/audio/rebroadcastLatency/mode"):
        entities.append(
            BoseRebroadcastLatencyModeSelect(speaker, system_info, config_entry, hass)
        )

    if speaker.has_capability("/cec"):
        entities.append(BoseCecSettingsSelect(speaker, system_info, config_entry, hass))

    async_add_entities(entities, update_before_add=False)


class BoseBaseSelect(BoseBaseEntity, SelectEntity):
    """Base class for Bose device selectors."""

    _set_method: str = ""
    _get_method: str = ""
    _value_key: str = ""
    _supported_key: str = ""
    _resource_path: str = ""
    _mode_class = object

    def __init__(
        self,
        speaker: BoseSpeaker,
        speaker_info,
        config_entry,
        mode_type,
        name_suffix,
        unique_id_suffix,
        hass: HomeAssistant,
    ) -> None:
        """Initialize the select entity."""
        BoseBaseEntity.__init__(self, speaker)
        self.speaker = speaker
        self.speaker_info = speaker_info
        self.config_entry = config_entry

        self._attr_translation_key = unique_id_suffix.replace("_select", "")
        self._attr_options = []
        self._attr_entity_category = EntityCategory.CONFIG

        self.speaker.attach_receiver(self._parse_message)

        hass.async_create_task(self.async_update())

    async def async_select_option(self, option: str) -> None:
        """Change the audio mode on the speaker."""

        for real_option, huminzed_option in HUMINZED_OPTIONS.items():
            if option == huminzed_option:
                option = real_option
                break

        await getattr(self.speaker, self._set_method)(option)

    def _parse_audio_mode(self, data, mode_type):
        selected_audio = data.get(self._value_key)
        supported = data.get("properties", {}).get(self._supported_key, [])
        self._attr_options = [
            str(HUMINZED_OPTIONS.get(option, option))
            for option in supported
            if option is not None
        ]

        if HUMINZED_OPTIONS.get(selected_audio):
            self._attr_current_option = HUMINZED_OPTIONS.get(selected_audio)
        else:
            self._attr_current_option = selected_audio

        if self.hass:
            self.async_write_ha_state()

    def _parse_message(self, data):
        """Parse real-time messages from the speaker."""
        if data.get("header", {}).get("resource") == self._resource_path:
            self._parse_audio_mode(data.get("body", {}), self._mode_class)

    async def async_update(self) -> None:
        """Fetch the current audio mode."""
        data = await getattr(self.speaker, self._get_method)()
        self._parse_audio_mode(data, self._mode_class)


class BoseAudioSelect(BoseBaseSelect):
    """Representation of a Bose device audio selector."""

    _set_method = "set_audio_mode"
    _get_method = "get_audio_mode"
    _value_key = "value"
    _supported_key = "supportedValues"
    _resource_path = "/audio/mode"
    _mode_class = AudioMode

    def __init__(
        self, speaker, speaker_info, config_entry, hass: HomeAssistant
    ) -> None:
        """Initialize the select entity."""
        super().__init__(
            speaker,
            speaker_info,
            config_entry,
            AudioMode,
            "Audio",
            "audio_select",
            hass,
        )
        self._attr_translation_key = "audio_mode"


class BoseDualMonoSelect(BoseBaseSelect):
    """Representation of a Bose device dual mono selector."""

    _set_method = "set_dual_mono_setting"
    _get_method = "get_dual_mono_setting"
    _value_key = "value"
    _supported_key = "supportedValues"
    _resource_path = "/audio/dualMonoSelect"
    _mode_class = DualMonoSettings

    def __init__(
        self, speaker, speaker_info, config_entry, hass: HomeAssistant
    ) -> None:
        """Initialize the select entity."""
        super().__init__(
            speaker,
            speaker_info,
            config_entry,
            DualMonoSettings,
            "Dual Mono",
            "dual_mono_select",
            hass,
        )
        self._attr_translation_key = "dual_mono"


class BoseRebroadcastLatencyModeSelect(BoseBaseSelect):
    """Representation of a Bose device rebroadcast latency mode selector."""

    _set_method = "set_rebroadcast_latency_mode"
    _get_method = "get_rebroadcast_latency_mode"
    _value_key = "mode"
    _supported_key = "supportedModes"
    _resource_path = "/audio/rebroadcastLatency/mode"
    _mode_class = RebroadcastLatencyMode

    def __init__(
        self, speaker, speaker_info, config_entry, hass: HomeAssistant
    ) -> None:
        """Initialize the select entity."""
        super().__init__(
            speaker,
            speaker_info,
            config_entry,
            RebroadcastLatencyMode,
            "Rebroadcast Latency Mode",
            "rebroadcast_latency_mode_select",
            hass,
        )
        self._attr_translation_key = "rebroadcast_latency"


class BoseCecSettingsSelect(BoseBaseSelect):
    """Representation of a Bose device CEC settings selector."""

    _set_method = "set_cec_settings"
    _get_method = "get_cec_settings"
    _value_key = "mode"
    _supported_key = "supportedModes"
    _resource_path = "/cec"
    _mode_class = CecSettings

    def __init__(
        self, speaker, speaker_info, config_entry, hass: HomeAssistant
    ) -> None:
        """Initialize the select entity."""
        super().__init__(
            speaker,
            speaker_info,
            config_entry,
            CecSettings,
            "CEC",
            "cec_settings_select",
            hass,
        )
        self._attr_translation_key = "cec_settings"
