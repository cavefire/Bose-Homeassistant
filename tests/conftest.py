"""Shared fixtures for the Bose integration tests."""

import asyncio
import os
from pathlib import Path
import sys
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# The integration is imported as a plain package named "bose", the way Home
# Assistant loads it from custom_components.
sys.path.insert(0, str(REPO_ROOT / "custom_components"))

# pybose is a runtime requirement of the integration. Allow pointing at a local
# source checkout so the tests can run without installing the release.
if (pybose_path := os.environ.get("PYBOSE_PATH")) is not None:
    sys.path.insert(0, pybose_path)

try:
    import pybose  # noqa: F401
except ImportError as err:  # pragma: no cover - environment problem
    raise ImportError(
        "pybose is required to run these tests. Install it with "
        "`pip install pybose` or set PYBOSE_PATH to a source checkout."
    ) from err


class FakeSpeaker:
    """Minimal stand-in for pybose's BoseSpeaker."""

    def __init__(
        self,
        capabilities: tuple[str, ...] = (),
        values: dict[str, Any] | None = None,
        known_options: tuple[str, ...] = (),
    ) -> None:
        """Initialize the fake speaker."""
        self.capabilities = capabilities
        # Bodies returned per resource, e.g. {"/audio/bass": {"value": 3}}.
        self.values = values or {}
        # Options pybose's own getters/setters accept; everything else raises,
        # like BoseInvalidAudioSettingException does for unknown settings.
        self.known_options = known_options
        self.receivers: list[Any] = []
        self.requests: list[dict[str, Any]] = []
        self.settings: dict[str, int] = {}
        self.hangs = False

    def get_device_id(self) -> str:
        """Return a stable device id."""
        return "device-1"

    def attach_receiver(self, callback) -> None:
        """Register a notification callback."""
        self.receivers.append(callback)

    def has_capability(self, resource: str) -> bool:
        """Return whether the speaker advertises a resource."""
        return resource in self.capabilities

    def notify(self, resource: str, body: dict[str, Any]) -> None:
        """Deliver a notification to every registered receiver."""
        for callback in self.receivers:
            callback({"header": {"resource": resource}, "body": body})

    async def get_system_info(self) -> dict[str, Any]:
        """Return the system info."""
        return self.values.get("/system/info", {})

    async def get_audio_setting(self, option: str) -> dict[str, Any]:
        """Read a sound setting, rejecting the ones pybose does not know."""
        if option not in self.known_options:
            raise ValueError(f"Invalid audio setting {option}")
        return self.values[f"/audio/{option}"]

    async def set_audio_setting(self, option: str, value: int) -> dict[str, Any]:
        """Write a sound setting, rejecting the ones pybose does not know."""
        if option not in self.known_options:
            raise ValueError(f"Invalid audio setting {option}")
        self.settings[option] = value
        return {"value": value}

    async def _request(
        self,
        resource: str,
        method: str,
        body: dict[str, Any] | None = None,
        checkCapabilities: bool = True,  # pybose's spelling
    ) -> dict[str, Any]:
        """Record a raw request and answer it from the configured values."""
        self.requests.append(
            {
                "resource": resource,
                "method": method,
                "body": body,
                "checkCapabilities": checkCapabilities,
            }
        )
        if self.hangs:
            # A speaker stays quiet about resources it does not implement, and
            # pybose then waits for a response forever.
            await asyncio.Event().wait()
        if checkCapabilities and not self.has_capability(resource):
            raise ValueError(f"Resource {resource} is not supported by the device.")
        if method == "POST":
            self.settings[resource.removeprefix("/audio/")] = (body or {})["value"]
            return body or {}
        return self.values[resource]


class FakeCoordinator:
    """Minimal stand-in for BoseCoordinator."""

    def __init__(self, speaker: FakeSpeaker) -> None:
        """Initialize the fake coordinator."""
        self.speaker = speaker

    async def get_audio_setting(self, option: str) -> dict[str, Any]:
        """Delegate to the speaker, like the real coordinator does."""
        return await self.speaker.get_audio_setting(option)

    async def get_audio_format(self) -> dict[str, Any]:
        """Delegate to the speaker, like the real coordinator does."""
        return await self.speaker._request("/audio/format", "GET")  # noqa: SLF001


class FakeHass:
    """Just enough of HomeAssistant for entity construction."""

    def __init__(self) -> None:
        """Initialize the fake hass."""
        self.tasks: list[Any] = []

    def async_create_task(self, coro, *args, **kwargs) -> None:
        """Swallow the start-up refresh so tests can drive it explicitly."""
        coro.close()


@pytest.fixture
def speaker() -> FakeSpeaker:
    """Return a fake speaker."""
    return FakeSpeaker()


@pytest.fixture
def hass() -> FakeHass:
    """Return a fake Home Assistant instance."""
    return FakeHass()


@pytest.fixture
def tv_now_playing() -> dict:
    """Now playing as reported while the TV input is active."""
    return {
        "source": {"sourceID": "PRODUCT", "sourceDisplayName": "TV"},
        "container": {"contentItem": {"source": "PRODUCT", "sourceAccount": "TV"}},
        "state": {"status": "PLAY"},
    }


@pytest.fixture
def bluetooth_now_playing() -> dict:
    """Now playing as reported while a Bluetooth device streams."""
    return {
        "source": {"sourceID": "BLUETOOTH", "sourceDisplayName": "Bluetooth"},
        "state": {"status": "PLAY"},
    }
