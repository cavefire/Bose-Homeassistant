"""Tests for setting up a config entry."""

import time
from types import SimpleNamespace

import bose
from bose import async_setup_entry
import jwt
import pytest

from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .conftest import FakeHass


def _token(expires_in: int) -> str:
    """Return a JWT that expires in the given number of seconds."""
    return jwt.encode({"exp": int(time.time()) + expires_in}, "key", algorithm="HS256")


VALID_TOKEN = _token(8 * 3600)
EXPIRED_TOKEN = _token(-3600)

ENTRY_DATA = {
    "mail": "user@example.com",
    "ip": "1.2.3.4",
    "guid": "guid-1",
    "access_token": VALID_TOKEN,
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


def _entry(**data):
    return SimpleNamespace(
        entry_id="e1",
        title="Kitchen",
        unique_id="guid-1",
        data={**ENTRY_DATA, **data},
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


async def test_expired_token_is_refreshed_before_connecting(monkeypatch):
    """An expired token is refreshed first, so the speaker accepts the connection."""
    calls = []

    async def refreshes(hass, entry, auth):
        calls.append("refresh")
        auth.set_access_token(VALID_TOKEN, "r2", "p")
        return True

    async def cannot_connect(hass, entry, auth):
        calls.append(("connect", auth.getCachedToken()["access_token"]))

    monkeypatch.setattr(bose, "refresh_token", refreshes)
    monkeypatch.setattr(bose, "connect_to_bose", cannot_connect)

    with pytest.raises(ConfigEntryNotReady):
        await async_setup_entry(_hass(), _entry(access_token=EXPIRED_TOKEN))

    assert calls[:2] == ["refresh", ("connect", VALID_TOKEN)]


async def test_failed_refresh_of_expired_token_asks_for_a_retry(monkeypatch):
    """A refresh that fails for a temporary reason is retried, not a reauth."""

    async def fails(hass, entry, auth):
        return False

    async def must_not_connect(hass, entry, auth):
        raise AssertionError("connected with an expired token")

    monkeypatch.setattr(bose, "refresh_token", fails)
    monkeypatch.setattr(bose, "connect_to_bose", must_not_connect)
    hass = _hass()

    with pytest.raises(ConfigEntryNotReady):
        await async_setup_entry(hass, _entry(access_token=EXPIRED_TOKEN))

    assert hass.tasks == []


async def test_rejected_refresh_token_asks_for_reauthentication(monkeypatch):
    """A rejected refresh token starts the reauthentication flow."""

    async def rejected(hass, entry, auth):
        raise ConfigEntryAuthFailed("Refresh token invalid")

    monkeypatch.setattr(bose, "refresh_token", rejected)

    with pytest.raises(ConfigEntryAuthFailed):
        await async_setup_entry(_hass(), _entry(access_token=EXPIRED_TOKEN))


async def test_valid_token_is_not_refreshed(monkeypatch):
    """A valid token is used as is, even if the speaker is unreachable."""

    async def must_not_refresh(hass, entry, auth):
        raise AssertionError("refreshed a valid token")

    async def cannot_connect(hass, entry, auth):
        return None

    monkeypatch.setattr(bose, "refresh_token", must_not_refresh)
    monkeypatch.setattr(bose, "connect_to_bose", cannot_connect)

    with pytest.raises(ConfigEntryNotReady):
        await async_setup_entry(_hass(), _entry())
