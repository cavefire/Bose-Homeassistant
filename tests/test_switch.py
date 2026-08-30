"""Tests for the Bose switch platform."""

from bose.switch import BoseAccessorySwitch, BoseStandbySettingSwitch

from .conftest import FakeHass, FakeSpeaker


def _accessory_switch(speaker):
    entity = BoseAccessorySwitch(
        speaker,
        {"productName": "Test"},
        {"enabled": {"subs": True}},
        None,
        "Subwoofers",
        "subs",
    )
    entity.async_write_ha_state = lambda: None
    return entity


async def _no_answer():
    raise TimeoutError("no response from the speaker within 10 seconds")


async def test_failed_update_goes_unavailable_instead_of_raising():
    """A speaker that does not answer must not break the poll (issue #82)."""
    speaker = FakeSpeaker()
    speaker.get_accessories = _no_answer
    entity = _accessory_switch(speaker)

    await entity.async_update()

    assert not entity.available


async def test_update_recovers_when_the_speaker_answers_again():
    """Availability comes back with the first successful read."""
    speaker = FakeSpeaker()

    async def answers():
        return {"enabled": {"subs": False}}

    speaker.get_accessories = answers
    entity = _accessory_switch(speaker)
    entity._attr_available = False  # noqa: SLF001

    await entity.async_update()

    assert entity.available
    assert entity.is_on is False


async def test_push_restores_availability():
    """A notification proves the speaker is alive again."""
    speaker = FakeSpeaker()
    entity = _accessory_switch(speaker)
    entity._attr_available = False  # noqa: SLF001

    speaker.notify("/accessories", {"enabled": {"subs": True}})

    assert entity.available
    assert entity.is_on is True


async def test_standby_switch_survives_a_failed_update():
    """The standby switch gets the same protection."""
    speaker = FakeSpeaker()
    speaker.get_system_timeout = _no_answer
    entity = BoseStandbySettingSwitch(
        speaker, {"productName": "Test"}, None, FakeHass()
    )
    entity.async_write_ha_state = lambda: None

    await entity.async_update()

    assert not entity.available
