"""Tests for source tracking on the Bose media player."""

from bose.media_player import BoseMediaPlayer
from pybose.BoseResponse import ContentNowPlaying

PHONE = {"mac": "AA:BB", "name": "Phone", "deviceClass": "phone"}
SINK_STATUS_WITH_PHONE = {"activeDevice": "AA:BB", "devices": [PHONE]}


def _player(source: str, now_playing: dict) -> BoseMediaPlayer:
    """Build a media player mid-flight, without its full setup."""
    player = object.__new__(BoseMediaPlayer)
    player._attr_source = source  # noqa: SLF001
    player._attr_source_list = ["TV", "Optical"]  # noqa: SLF001
    player._bluetooth_devices = {}  # noqa: SLF001
    player._source_renames = {}  # noqa: SLF001
    player._now_playing_result = ContentNowPlaying(now_playing)  # noqa: SLF001
    return player


def test_connected_phone_does_not_override_tv(tv_now_playing):
    """A phone that stays connected must not snap the source back (issue #93)."""
    player = _player("TV", tv_now_playing)

    player._parse_bluetooth_sink_status(SINK_STATUS_WITH_PHONE)  # noqa: SLF001

    assert player.source == "TV"
    # The phone is still offered as a source to switch back to.
    assert "Bluetooth: Phone" in player.source_list


def test_playing_phone_becomes_the_source(bluetooth_now_playing):
    """When Bluetooth is what plays, the connected device is the source."""
    player = _player("TV", bluetooth_now_playing)

    player._parse_bluetooth_sink_status(SINK_STATUS_WITH_PHONE)  # noqa: SLF001

    assert player.source == "Bluetooth: Phone"


def test_source_list_keeps_product_inputs_when_phone_connects(tv_now_playing):
    """Connecting a phone adds it to the list without dropping TV."""
    player = _player("TV", tv_now_playing)

    player._parse_bluetooth_sink_status(SINK_STATUS_WITH_PHONE)  # noqa: SLF001

    assert player.source_list == ["TV", "Optical", "Bluetooth: Phone"]
