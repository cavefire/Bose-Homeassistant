"""The Bose component."""

from pybose.BoseAuth import BoseAuth
from pybose.BoseSpeaker import BoseSpeaker

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Bose integration from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Store device data in a separate dict (instead of modifying config_entry.data)
    hass.data[DOMAIN][config_entry.entry_id] = {
        "config": config_entry.data  # Store configuration data
    }

    # Offload token validation to avoid blocking the event loop
    is_token_valid = await hass.async_add_executor_job(
        _check_token_validity, config_entry.data.get("access_token")
    )

    if not is_token_valid:
        new_access_token = await hass.async_add_executor_job(
            _fetch_access_token,
            config_entry.data["mail"],
            config_entry.data["password"],
        )

        # Update the config entry properly using Home Assistant's API
        hass.config_entries.async_update_entry(
            config_entry,
            data={**config_entry.data, "access_token": new_access_token},
        )

    speaker = await connect_to_bose(config_entry)
    system_info = await speaker.get_system_info()
    sub = await speaker.subscribe()

    # Register device in Home Assistant
    device_registry = dr.async_get(hass)

    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, config_entry.data["guid"])},  # Unique device identifier
        manufacturer="Bose",
        name=system_info.name,
        model=system_info.productName,
        serial_number=system_info.serialNumber,
        sw_version=system_info.softwareVersion,
        configuration_url=f"https://{config_entry.data['ip']}",
    )

    # Store the speaker object separately
    hass.data[DOMAIN][config_entry.entry_id]["speaker"] = speaker

    # Forward to media player platform
    await hass.config_entries.async_forward_entry_setups(config_entry, ["media_player"])
    return True


def _check_token_validity(access_token: str) -> bool:
    """Check if the Bose access token is still valid."""
    return BoseAuth().is_token_valid(access_token)


def _fetch_access_token(email: str, password: str) -> str:
    """Fetch a new Bose access token using blocking requests."""
    auth = BoseAuth()
    token_response = auth.getControlToken(email, password)
    return token_response["access_token"]


async def connect_to_bose(config_entry):
    """Connect to the Bose speaker."""
    data = config_entry.data
    speaker = BoseSpeaker(
        control_token=data["access_token"],
        host=data["ip"],
    )

    await speaker.connect()
    return speaker
