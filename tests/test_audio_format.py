"""Tests for the Bose audio format sensor and media player attribute."""

import json

from bose.bose.audioformat import AUDIO_FORMAT_RESOURCE, format_audio_codec
from bose.media_player import BoseMediaPlayer
from bose.sensor import BoseAudioFormatSensor
import pytest

from .conftest import REPO_ROOT, FakeCoordinator, FakeSpeaker

TRANSLATION_FILES = [
    REPO_ROOT / "custom_components/bose/strings.json",
    *sorted((REPO_ROOT / "custom_components/bose/translations").glob("*.json")),
]


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        (None, None),
        ({}, None),
        ({"format": "Dolby Atmos", "channels": "5.1.2"}, "Dolby Atmos · 5.1.2"),
        ({"type": "PCM", "channels": "2.0"}, "PCM · 2.0"),
        ({"format": "PCM"}, "PCM"),
        # A channel count without a codec says nothing useful.
        ({"channels": "2.0"}, None),
        # "format" wins over the legacy "type" key.
        ({"format": "DTS", "type": "PCM"}, "DTS"),
    ],
)
def test_format_audio_codec(body, expected):
    """The codec description is built from whichever keys the speaker sends."""
    assert format_audio_codec(body) == expected


@pytest.mark.parametrize("translation_file", TRANSLATION_FILES, ids=lambda p: p.name)
def test_audio_format_sensor_is_translated(translation_file):
    """The sensor has a name in every language."""
    names = json.loads(translation_file.read_text())["entity"]["sensor"]
    assert "audio_format" in names


def _sensor(speaker, hass):
    """Build the audio format sensor around the fakes."""
    return BoseAudioFormatSensor(
        speaker,
        type("Entry", (), {"data": {"ip": "1.2.3.4", "guid": "guid-1"}})(),
        hass,
        FakeCoordinator(speaker),
    )


async def test_sensor_reads_the_current_format(hass):
    """The sensor picks up the format the speaker reports."""
    speaker = FakeSpeaker(
        capabilities=(AUDIO_FORMAT_RESOURCE,),
        values={AUDIO_FORMAT_RESOURCE: {"format": "Dolby Digital", "channels": "5.1"}},
    )
    sensor = _sensor(speaker, hass)
    sensor.hass = hass

    await sensor.async_update()

    assert sensor.native_value == "Dolby Digital · 5.1"


async def test_sensor_follows_notifications(hass):
    """A pushed format updates the sensor."""
    speaker = FakeSpeaker(capabilities=(AUDIO_FORMAT_RESOURCE,), values={})
    sensor = _sensor(speaker, hass)
    assert sensor.entity_id is None

    # Would raise NoEntitySpecifiedError if the state was written straight away.
    speaker.notify(AUDIO_FORMAT_RESOURCE, {"format": "PCM", "channels": "2.0"})

    assert sensor.native_value == "PCM · 2.0"


async def test_sensor_ignores_other_resources(hass):
    """Unrelated notifications leave the sensor alone."""
    speaker = FakeSpeaker(capabilities=(AUDIO_FORMAT_RESOURCE,), values={})
    sensor = _sensor(speaker, hass)

    speaker.notify("/audio/volume", {"value": 20})

    assert sensor.native_value is None


def _media_player() -> BoseMediaPlayer:
    """Build a media player without going through its full setup."""
    player = object.__new__(BoseMediaPlayer)
    player._audio_codec = None  # noqa: SLF001
    player.async_write_ha_state = lambda: None
    return player


def test_media_player_reports_the_codec():
    """The media player exposes the codec as an attribute."""
    player = _media_player()

    player.parse_message(
        {
            "header": {"resource": AUDIO_FORMAT_RESOURCE},
            "body": {"format": "Dolby Atmos", "channels": "5.1.2"},
        }
    )

    assert player.extra_state_attributes == {"audio_codec": "Dolby Atmos · 5.1.2"}


def test_media_player_clears_the_codec_when_switched_off():
    """A stale codec must not survive the speaker being turned off."""
    player = _media_player()
    player.parse_message(
        {
            "header": {"resource": AUDIO_FORMAT_RESOURCE},
            "body": {"format": "Dolby Atmos", "channels": "5.1.2"},
        }
    )

    player.parse_message(
        {"header": {"resource": "/system/power/control"}, "body": {"power": "OFF"}}
    )

    assert player.extra_state_attributes == {"audio_codec": None}
