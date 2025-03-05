"""Support for Bose source selection."""

from pybose.BoseResponse import ContentNowPlaying, Sources
from pybose.BoseSpeaker import BoseSpeaker

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

# Chromecast, Alexa, Airplay, (Spotify??) can not be set, only detected
# I dont have a spotify account, so I can't test that. Feel free :)
AVAILABLE_SOURCES = {
    "Group": {"source": "GROUPING", "sourceAccount": "grouping@bose.com"},
    "Spotify": {"source": "SPOTIFY", "sourceAccount": "SpotifyConnectUserName"},
    "SpotifyAlexa": {"source": "SPOTIFY", "sourceAccount": "SpotifyAlexaUserName"},
    # "Chromecast": {
    #    "source": "CHROMECASTBUILTIN",
    #    "sourceAccount": "chromecast_builtin@bose.com",
    # },
    # "Alexa": {"source": "ALEXA", "sourceAccount": "alexauser@bose.com"},
    # "AirPlay": {"source": "AIRPLAY", "sourceAccount": "AirPlay2DefaultUserName"},
    "UPNP": {"source": "UPNP", "sourceAccount": "UPnPUserName"},
    "QPlay": {"source": "QPLAY", "sourceAccount": "QPlay1UserName"},  # What is that?
    "QPlay2": {"source": "QPLAY2", "sourceAccount": "QPlay2UserName"},  # What is that?
    "Optical": {"source": "PRODUCT", "sourceAccount": "AUX_DIGITAL"},
    "Cinch": {"source": "PRODUCT", "sourceAccount": "AUX_ANALOG"},
    "TV": {"source": "PRODUCT", "sourceAccount": "TV"},
    # TODO - Add support for these sources
    # "Bluetooth": {"source": "BLUETOOTH", "sourceAccount": ""}
    # "TuneIn": {"source": "TUNEIN", "sourceAccount": ""}
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bose select entity."""
    speaker = hass.data[DOMAIN][config_entry.entry_id]["speaker"]
    system_info = hass.data[DOMAIN][config_entry.entry_id]["system_info"]

    # Fetch sources
    sources = await speaker.get_sources()

    # Add select entity with device info
    entity = BoseSourceSelect(speaker, system_info, config_entry, sources)
    async_add_entities([entity])

    # Ensure state update only happens after HA registers the entity
    await entity.async_update()


class BoseSourceSelect(SelectEntity):
    """Representation of a Bose device source selector."""

    def __init__(
        self, speaker: BoseSpeaker, speaker_info, config_entry, sources: Sources
    ) -> None:
        """Initialize the select entity."""
        self.speaker = speaker
        self._attr_name = f"{speaker_info.name} Source"
        self._attr_unique_id = f"{config_entry.data['guid']}_source_select"
        self.speaker_info = speaker_info
        self.config_entry = config_entry

        """
        TODO: find other way to filter sources.
            "TV" is "NOT_CONFIGURED" and not visible on some devices (e.g. Soundbar 500). 
            Including them for now, but should be changed in the future
        """
        self._attr_options = []
        for source in sources.sources:
            if (
                (source.status == "AVAILABLE" or source.status == "NOT_CONFIGURED")
                and source.sourceAccountName
                and source.sourceName
            ):
                for key, value in AVAILABLE_SOURCES.items():
                    if (
                        source.sourceName == value["source"]
                        and source.sourceAccountName == value["sourceAccount"]
                    ):
                        self._attr_options.append(key)

        self._selected_source = None

        self.speaker.attach_receiver(self._parse_message)

    async def async_select_option(self, option: str) -> None:
        """Change the source on the speaker."""
        if option in AVAILABLE_SOURCES:
            source_data = AVAILABLE_SOURCES[option]
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
        for source_name, source_data in AVAILABLE_SOURCES.items():
            if (
                data.container.contentItem.source == source_data["source"]
                and data.container.contentItem.sourceAccount
                == source_data["sourceAccount"]
            ):
                self._selected_source = source_name
                self.async_write_ha_state()
                return

        self._selected_source = None

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
            "name": self.speaker_info.name,
            "manufacturer": "Bose",
            "model": self.speaker_info.productName,
            "sw_version": self.speaker_info.softwareVersion,
        }
