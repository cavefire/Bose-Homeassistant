"""Tests for the Bose config flow."""

import asyncio

from bose import config_flow
from bose.config_flow import async_fetch_speaker_info
import pytest


class FakeFlowSpeaker:
    """A speaker as the config flow sees it."""

    instances: list = []
    # Whether the speaker answers at all; False mimics one that stays quiet.
    answers = True

    def __init__(self, bose_auth=None, host=None, **kwargs) -> None:
        """Record construction."""
        self.host = host
        self.disconnected = False
        FakeFlowSpeaker.instances.append(self)

    async def connect(self) -> None:
        """Connect, or hang forever like pybose does when the speaker stays quiet."""
        if not self.answers:
            await asyncio.Event().wait()

    async def get_system_info(self) -> dict:
        """Return the identity."""
        return {"name": "Kitchen", "serialNumber": "S1"}

    def get_device_id(self) -> str:
        """Return the guid."""
        return "guid-1"

    async def disconnect(self) -> None:
        """Remember the connection was closed."""
        self.disconnected = True


@pytest.fixture(autouse=True)
def _fake_speaker(monkeypatch):
    FakeFlowSpeaker.instances.clear()
    monkeypatch.setattr(config_flow, "BoseSpeaker", FakeFlowSpeaker)


async def test_fetch_speaker_info_returns_identity_and_disconnects():
    """The flow reads guid and system info, then lets go of the speaker."""
    guid, info = await async_fetch_speaker_info(None, "1.2.3.4")

    assert (guid, info["name"]) == ("guid-1", "Kitchen")
    assert FakeFlowSpeaker.instances[0].disconnected


async def test_fetch_speaker_info_gives_up_on_a_silent_speaker(monkeypatch):
    """A speaker that never answers must not hang the flow forever (issue #94)."""
    monkeypatch.setattr(config_flow, "CONNECT_TIMEOUT", 0.01)
    monkeypatch.setattr(FakeFlowSpeaker, "answers", False)

    async with asyncio.timeout(5):
        with pytest.raises(TimeoutError):
            await async_fetch_speaker_info(None, "1.2.3.4")

    assert FakeFlowSpeaker.instances[0].disconnected
