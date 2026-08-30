"""Tests for the audio codec reported by the Bose media player."""

from bose.media_player import AUDIO_FORMAT_RESOURCE, BoseMediaPlayer
import pytest

from .conftest import FakeCoordinator, FakeSpeaker


def _media_player(speaker: FakeSpeaker | None = None) -> BoseMediaPlayer:
    """Build a media player without going through its full setup."""
    speaker = speaker or FakeSpeaker()
    player = object.__new__(BoseMediaPlayer)
    player.speaker = speaker
    player.coordinator = FakeCoordinator(speaker)
    player._audio_codec = None  # noqa: SLF001
    player.async_write_ha_state = lambda: None
    return player


def _notify_format(player: BoseMediaPlayer, body: dict) -> None:
    """Deliver an /audio/format notification to the player."""
    player.parse_message({"header": {"resource": AUDIO_FORMAT_RESOURCE}, "body": body})


@pytest.mark.parametrize(
    ("body", "expected"),
    [
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
def test_codec_is_built_from_what_the_speaker_sends(body, expected):
    """The codec description uses whichever keys the speaker provides."""
    player = _media_player()

    _notify_format(player, body)

    assert player.extra_state_attributes == {"audio_codec": expected}


def test_codec_follows_notifications():
    """A pushed format replaces the previous one."""
    player = _media_player()

    _notify_format(player, {"format": "PCM", "channels": "2.0"})
    assert player.extra_state_attributes == {"audio_codec": "PCM · 2.0"}

    _notify_format(player, {"format": "Dolby Atmos", "channels": "5.1.2"})
    assert player.extra_state_attributes == {"audio_codec": "Dolby Atmos · 5.1.2"}


def test_codec_is_cleared_when_the_speaker_is_switched_off():
    """A stale codec must not survive the speaker being turned off."""
    player = _media_player()
    _notify_format(player, {"format": "Dolby Atmos", "channels": "5.1.2"})

    player.parse_message(
        {"header": {"resource": "/system/power/control"}, "body": {"power": "OFF"}}
    )

    assert player.extra_state_attributes == {"audio_codec": None}


async def test_codec_is_read_at_start_up():
    """The codec is known before the first notification arrives."""
    speaker = FakeSpeaker(
        capabilities=(AUDIO_FORMAT_RESOURCE,),
        values={AUDIO_FORMAT_RESOURCE: {"format": "Dolby Digital", "channels": "5.1"}},
    )
    player = _media_player(speaker)

    await player._refresh_audio_format()  # noqa: SLF001

    assert player.extra_state_attributes == {"audio_codec": "Dolby Digital · 5.1"}


async def test_speakers_without_the_capability_are_not_asked():
    """A speaker that does not report a format is left alone."""
    speaker = FakeSpeaker(capabilities=(), values={})
    player = _media_player(speaker)

    await player._refresh_audio_format()  # noqa: SLF001

    assert speaker.requests == []
    assert player.extra_state_attributes == {"audio_codec": None}


async def test_a_failed_read_does_not_break_the_update():
    """Losing the audio format must not take the whole media player down."""
    speaker = FakeSpeaker(capabilities=(AUDIO_FORMAT_RESOURCE,), values={})
    player = _media_player(speaker)

    await player._refresh_audio_format()  # noqa: SLF001

    assert player.extra_state_attributes == {"audio_codec": None}
