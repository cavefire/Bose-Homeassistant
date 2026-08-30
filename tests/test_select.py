"""Tests for the Bose select platform."""

from bose.select import BoseAudioSelect

from .conftest import FakeHass, FakeSpeaker


def _audio_select(speaker):
    entity = BoseAudioSelect(speaker, {"productName": "Test"}, None, FakeHass())
    entity.async_write_ha_state = lambda: None
    return entity


async def test_failed_update_goes_unavailable_instead_of_raising():
    """A speaker that does not answer must not break the poll (issue #82)."""
    speaker = FakeSpeaker()

    async def no_answer():
        raise TimeoutError("no response from the speaker within 10 seconds")

    speaker.get_audio_mode = no_answer
    entity = _audio_select(speaker)

    await entity.async_update()

    assert not entity.available


async def test_update_recovers_when_the_speaker_answers_again():
    """Availability comes back with the first successful read."""
    speaker = FakeSpeaker()

    async def answers():
        return {
            "value": "NORMAL",
            "properties": {"supportedValues": ["NORMAL", "DIALOG"]},
        }

    speaker.get_audio_mode = answers
    entity = _audio_select(speaker)
    entity._attr_available = False  # noqa: SLF001

    await entity.async_update()

    assert entity.available
    assert entity.current_option == "normal"


async def test_push_restores_availability():
    """A notification proves the speaker is alive again."""
    speaker = FakeSpeaker()
    entity = _audio_select(speaker)
    entity._attr_available = False  # noqa: SLF001

    speaker.notify(
        "/audio/mode",
        {"value": "DIALOG", "properties": {"supportedValues": ["DIALOG"]}},
    )

    assert entity.available
    assert entity.current_option == "dialog"
