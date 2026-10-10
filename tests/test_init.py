"""Tests for config entry setup helpers."""

from types import SimpleNamespace

import bose
from bose import async_migrate_unique_id, registerAccessories
from bose.const import DOMAIN


class FakeConfigEntries:
    """Just enough of hass.config_entries for the migration."""

    def __init__(self, entries) -> None:
        """Hold the entries."""
        self.entries = entries
        self.updates = []

    def async_entry_for_domain_unique_id(self, domain, unique_id):
        """Find the entry owning a unique id."""
        for entry in self.entries:
            if entry.unique_id == unique_id:
                return entry
        return None

    def async_update_entry(self, entry, **changes):
        """Record the update."""
        self.updates.append((entry.entry_id, changes))
        for key, value in changes.items():
            setattr(entry, key, value)
        return True


def _entry(entry_id, guid, unique_id=None):
    return SimpleNamespace(
        entry_id=entry_id, title=entry_id, unique_id=unique_id, data={"guid": guid}
    )


def _hass(*entries):
    return SimpleNamespace(config_entries=FakeConfigEntries(list(entries)))


def test_legacy_entry_gets_its_guid_as_unique_id():
    """Entries from before 1.2.3 are recognised by discovery afterwards (issue #94)."""
    legacy = _entry("old", "guid-1")
    hass = _hass(legacy)

    async_migrate_unique_id(hass, legacy)

    assert hass.config_entries.updates == [("old", {"unique_id": "guid-1"})]


def test_entry_with_unique_id_is_left_alone():
    """Nothing to do for entries created by newer versions."""
    entry = _entry("new", "guid-1", unique_id="guid-1")
    hass = _hass(entry)

    async_migrate_unique_id(hass, entry)

    assert hass.config_entries.updates == []


def test_duplicate_legacy_entry_is_not_given_the_same_unique_id():
    """Two entries for one speaker must not both claim its unique id."""
    keeper = _entry("keeper", "guid-1", unique_id="guid-1")
    duplicate = _entry("dup", "guid-1")
    hass = _hass(keeper, duplicate)

    async_migrate_unique_id(hass, duplicate)

    assert hass.config_entries.updates == []


def test_domain_is_used_for_the_lookup():
    """Sanity check the helper looks in our own domain."""
    assert DOMAIN == "bose"


class FakeDeviceRegistry:
    """Just enough of the device registry for registering accessories."""

    def __init__(self) -> None:
        """Start empty."""
        self.created = []
        self.updates = []
        self.devices = {}

    def async_get_or_create(self, **kwargs):
        """Create or return an accessory device."""
        self.created.append(kwargs)
        serial = next(iter(kwargs["identifiers"]))[1]
        return self.devices.setdefault(
            serial, SimpleNamespace(id=f"device-{serial}", via_device_id=None)
        )

    def async_update_device(self, device_id, **changes):
        """Record the update."""
        self.updates.append((device_id, changes))
        for device in self.devices.values():
            if device.id == device_id:
                device.via_device_id = changes["via_device_id"]


ACCESSORIES = {
    "subs": [{"serialnum": "SUB1", "type": "BASS_MODULE_700", "version": "1"}],
    "rears": [{"serialnum": "REAR1", "type": "SURROUND_SPEAKERS", "version": "1"}],
}


async def _register(monkeypatch, registry):
    monkeypatch.setattr(bose.dr, "async_get", lambda hass: registry)
    entry = SimpleNamespace(entry_id="e1", data={"guid": "guid-1"})
    await registerAccessories(SimpleNamespace(), entry, ACCESSORIES, "speaker-device")


async def test_accessories_are_linked_to_the_speaker(monkeypatch):
    """Accessories are linked without the deprecated via_device (issue #108)."""
    registry = FakeDeviceRegistry()

    await _register(monkeypatch, registry)

    assert [next(iter(c["identifiers"])) for c in registry.created] == [
        (DOMAIN, "SUB1"),
        (DOMAIN, "REAR1"),
    ]
    assert all("via_device" not in c for c in registry.created)
    assert registry.updates == [
        ("device-SUB1", {"via_device_id": "speaker-device"}),
        ("device-REAR1", {"via_device_id": "speaker-device"}),
    ]


async def test_accessories_already_linked_are_not_updated(monkeypatch):
    """Registering again does not rewrite an existing link."""
    registry = FakeDeviceRegistry()

    await _register(monkeypatch, registry)
    registry.updates.clear()
    await _register(monkeypatch, registry)

    assert registry.updates == []
