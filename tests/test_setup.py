"""Tests for setting up a config entry."""

from types import SimpleNamespace

import bose
from bose import async_setup_entry
import pytest

from homeassistant.exceptions import ConfigEntryNotReady

from .conftest import FakeHass

ENTRY_DATA = {
    "mail": "user@example.com",
    "ip": "1.2.3.4",
    "guid": "guid-1",
    "access_token": "a",
    "refresh_token": "r",
    "bose_person_id": "p",
    "azure_refresh_token": "z",
}


class FakeConfigEntries:
    """Just enough of hass.config_entries for setup."""

    def async_entry_for_domain_unique_id(self, domain, unique_id):
        """No other entry owns the unique id."""
        return

    def async_update_entry(self, entry, **changes):
        """Accept updates."""
        return True


class FakeSetupSpeaker:
    """A connected speaker that then fails to describe itself."""

    def __init__(self) -> None:
        """Start connected."""
        self.disconnected = False

    async def get_system_info(self):
        """Fail like a speaker that stops answering."""
        raise TimeoutError("no response from the speaker within 10 seconds")

    async def disconnect(self):
        """Remember the connection was closed."""
        self.disconnected = True


def _entry():
    return SimpleNamespace(
        entry_id="e1", title="Kitchen", unique_id="guid-1", data=dict(ENTRY_DATA)
    )


def _hass():
    hass = FakeHass()
    hass.config_entries = FakeConfigEntries()
    return hass


@pytest.fixture(autouse=True)
def _no_discovery(monkeypatch):
    async def nothing_found(hass):
        return []

    monkeypatch.setattr(bose.config_flow, "Discover_Bose_Devices", nothing_found)


async def test_unreachable_speaker_asks_for_a_retry(monkeypatch):
    """An unreachable speaker must not fail the entry for good (issue #95)."""

    async def cannot_connect(hass, entry, auth):
        return None

    monkeypatch.setattr(bose, "connect_to_bose", cannot_connect)
    hass = _hass()

    with pytest.raises(ConfigEntryNotReady):
        await async_setup_entry(hass, _entry())

    # Nothing long-running was left behind for the retry to duplicate.
    assert hass.tasks == []


async def test_speaker_that_stops_answering_asks_for_a_retry(monkeypatch):
    """A failure after connecting is retried too, and the socket is closed."""
    speaker = FakeSetupSpeaker()

    async def connects(hass, entry, auth):
        return speaker

    monkeypatch.setattr(bose, "connect_to_bose", connects)
    hass = _hass()

    with pytest.raises(ConfigEntryNotReady):
        await async_setup_entry(hass, _entry())

    assert speaker.disconnected
    assert hass.tasks == []
