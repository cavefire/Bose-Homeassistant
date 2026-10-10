"""Tests for the sensor platform."""

from types import SimpleNamespace

from bose import sensor
from pybose.BoseSpeaker import BoseRequestException

from .conftest import FakeHass, FakeSpeaker

NETWORK_STATUS = {
    "primary": "ETHERNET",
    "interfaces": [{"type": "ETHERNET", "state": "UP", "ipInfo": {}}],
}


class NetworkCoordinator:
    """Coordinator answering /network/status with a body or an exception."""

    def __init__(self, network_status) -> None:
        """Hold the response."""
        self.network_status = network_status

    async def get_network_status(self):
        """Return or raise the configured network status."""
        if isinstance(self.network_status, Exception):
            raise self.network_status
        return self.network_status


async def _setup_sensors(network_status) -> list:
    hass = FakeHass()
    hass.data = {
        "bose": {
            "e1": {
                "speaker": FakeSpeaker(capabilities=("/network/status",)),
                "coordinator": NetworkCoordinator(network_status),
            }
        }
    }
    entry = SimpleNamespace(entry_id="e1", data={"ip": "1.2.3.4", "guid": "guid-1"})
    added = []
    await sensor.async_setup_entry(
        hass, entry, lambda entities, **kwargs: added.extend(entities)
    )
    return added


async def test_network_sensors_are_added():
    """A readable network status adds the network type and IP sensors."""
    added = await _setup_sensors(NETWORK_STATUS)

    assert [type(entity).__name__ for entity in added] == [
        "BoseNetworkTypeSensor",
        "BoseNetworkIpSensor",
    ]


async def test_no_network_sensors_when_status_is_refused():
    """A speaker refusing /network/status gets no network sensors (issue #112).

    They could never be updated and would log an error on every poll.
    """
    refused = BoseRequestException(
        "GET", "/network/status", {}, 403, 0, "User not authorized for LAN"
    )

    assert await _setup_sensors(refused) == []
