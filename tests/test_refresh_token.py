"""Tests for refreshing the Bose access token."""

from types import SimpleNamespace

import bose
from bose import refresh_token
from pybose.BoseAuth import BoseAuth, BoseAuthRejectedError, BoseAuthUnavailableError
import pytest

from homeassistant.exceptions import ConfigEntryAuthFailed

from .conftest import FakeHass


class FakeConfigEntries:
    """Record config entry updates."""

    def __init__(self) -> None:
        """Start without updates."""
        self.updates: list[dict] = []

    def async_update_entry(self, entry, data=None, **changes):
        """Remember the new data."""
        self.updates.append(data)
        return True


class RefreshHass(FakeHass):
    """FakeHass that runs executor jobs inline."""

    def __init__(self) -> None:
        """Set up config entries."""
        super().__init__()
        self.config_entries = FakeConfigEntries()

    async def async_add_executor_job(self, func, *args):
        """Run the job directly."""
        return func(*args)


def _entry():
    return SimpleNamespace(
        entry_id="e1",
        data={
            "mail": "user@example.com",
            "access_token": "a",
            "refresh_token": "r",
            "azure_refresh_token": "z",
        },
    )


def _auth(monkeypatch, result):
    auth = BoseAuth()
    auth.set_azure_refresh_token("z2")

    def do_token_refresh():
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(auth, "do_token_refresh", do_token_refresh)
    monkeypatch.setattr(auth, "get_token_validity_time", lambda: 28800)
    return auth


async def test_refreshed_tokens_are_stored(monkeypatch):
    """A successful refresh stores the new tokens in the config entry."""
    hass = RefreshHass()
    auth = _auth(
        monkeypatch,
        {"access_token": "a2", "refresh_token": "r2", "bose_person_id": "p"},
    )

    assert await refresh_token(hass, _entry(), auth)

    [update] = hass.config_entries.updates
    assert update["access_token"] == "a2"
    assert update["refresh_token"] == "r2"
    assert update["azure_refresh_token"] == "z2"


async def test_rejected_refresh_token_asks_for_reauthentication(monkeypatch):
    """A refresh token Bose rejected requires logging in again."""
    hass = RefreshHass()
    auth = _auth(monkeypatch, BoseAuthRejectedError("HTTP 400"))

    with pytest.raises(ConfigEntryAuthFailed):
        await refresh_token(hass, _entry(), auth)

    assert hass.config_entries.updates == []


@pytest.mark.parametrize(
    "error",
    [
        BoseAuthUnavailableError("Failed to refresh Azure AD B2C tokens: DNS failure"),
        RuntimeError("unexpected"),
    ],
)
async def test_unavailable_login_service_is_retried_later(monkeypatch, error):
    """Bose being unreachable must not force a new login."""
    hass = RefreshHass()
    auth = _auth(monkeypatch, error)

    assert not await refresh_token(hass, _entry(), auth)
    assert hass.config_entries.updates == []


def test_requires_pybose_with_refresh_error_types():
    """The manifest pins a pybose release that reports why a refresh failed."""
    assert issubclass(BoseAuthRejectedError, ValueError)
    assert bose.BoseAuthRejectedError is BoseAuthRejectedError


class StopLoop(Exception):
    """Ends the refresh loop after a number of sleeps."""


async def _run_refresh_loop(monkeypatch, validity_times, sleeps=3):
    """Run refresh_token_thread until it slept `sleeps` times; return the refreshes."""
    refreshes = []
    slept = []

    async def fake_sleep(seconds):
        slept.append(seconds)
        if len(slept) >= sleeps:
            raise StopLoop

    async def fake_refresh(hass, entry, auth):
        refreshes.append(True)
        return True

    validity = iter(validity_times)
    auth = SimpleNamespace(get_token_validity_time=lambda: next(validity))
    monkeypatch.setattr(bose.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(bose, "refresh_token", fake_refresh)

    with pytest.raises(StopLoop):
        await bose.refresh_token_thread(RefreshHass(), _entry(), auth)
    return refreshes, slept


async def test_valid_token_is_not_refreshed_by_the_loop(monkeypatch):
    """A token valid for many hours is only checked again, not refreshed (issue #109)."""
    refreshes, slept = await _run_refresh_loop(monkeypatch, [8 * 3600] * 10)

    assert refreshes == []
    assert slept == [bose.TOKEN_REFRESH_DELAY] * 3


async def test_token_close_to_expiry_is_refreshed_by_the_loop(monkeypatch):
    """A token valid for less than two refresh delays is refreshed right away."""
    refreshes, slept = await _run_refresh_loop(
        monkeypatch, [3600, 8 * 3600, 8 * 3600, 8 * 3600], sleeps=2
    )

    assert refreshes == [True]
    assert slept == [bose.TOKEN_RETRY_DELAY, bose.TOKEN_REFRESH_DELAY]
