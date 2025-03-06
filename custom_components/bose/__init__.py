"""The Bose component."""

import json
import logging

from pybose.BoseAuth import BoseAuth
from pybose.BoseResponse import Accessories, BoseApiProduct
from pybose.BoseSpeaker import BoseSpeaker

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.helpers import config_validation as cv, device_registry as dr

from . import config_flow
from .const import DOMAIN

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Bose integration from a config entry."""
    auth = BoseAuth()

    hass.data.setdefault(DOMAIN, {})

    # Store device data in a separate dict (instead of modifying config_entry.data)
    hass.data[DOMAIN][config_entry.entry_id] = {
        "config": config_entry.data  # Store configuration data
    }

    # Offload token validation to avoid blocking the event loop
    is_token_valid = await hass.async_add_executor_job(
        auth.is_token_valid, config_entry.data.get("access_token")
    )

    if not is_token_valid or config_entry.data.get("bose_person_id", None) is None:
        login_result = await hass.async_add_executor_job(
            auth.getControlToken,
            config_entry.data["mail"],
            config_entry.data["password"],
            True,
        )

        print(login_result)

        # Update the config entry properly using Home Assistant's API
        hass.config_entries.async_update_entry(
            config_entry,
            data={
                **config_entry.data,
                "access_token": login_result["access_token"],
                "refresh_token": login_result["refresh_token"],
                "bose_person_id": login_result["bose_person_id"],
            },
        )

    speaker = await connect_to_bose(config_entry)

    if not speaker:
        discovered = await config_flow.Discover_Bose_Devices(hass)
        found = False

        # find the devce with the same GUID
        for device in discovered:
            if device["guid"] == config_entry.data["guid"]:
                logging.error(
                    "Found device with same GUID, updating IP to: %s", device["ip"]
                )
                hass.config_entries.async_update_entry(
                    config_entry,
                    data={**config_entry.data, "ip": device["ip"]},
                )
                found = True
                break

        if not found:
            logging.error(
                "Failed to connect to Bose speaker. No new ip was found, so assuming the device is offline."
            )
            return False

        config_entry = hass.config_entries.async_get_entry(config_entry.entry_id)
        speaker = await connect_to_bose(config_entry)

    system_info = await speaker.get_system_info()
    capabilities = await speaker.get_capabilities()
    await speaker.subscribe()

    # Register device in Home Assistant
    device_registry = dr.async_get(hass)

    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, config_entry.data["guid"])},
        manufacturer="Bose",
        name=system_info["name"],
        model=system_info["productName"],
        serial_number=system_info["serialNumber"],
        sw_version=system_info["softwareVersion"],
        configuration_url=f"https://{config_entry.data['ip']}",
    )

    # Store the speaker object separately
    hass.data[DOMAIN][config_entry.entry_id]["speaker"] = speaker
    hass.data[DOMAIN][config_entry.entry_id]["system_info"] = system_info
    hass.data[DOMAIN][config_entry.entry_id]["capabilities"] = capabilities
    hass.data[DOMAIN][config_entry.entry_id]["auth"] = auth


    
    try: 
        # Not all Devices have accessories like "Bose Portable Smart Speaker"
        accessories = await speaker.get_accessories()
        await registerAccessories(hass, config_entry, accessories)
    except Exception:  # noqa: BLE001
        accessories = []
    hass.data[DOMAIN][config_entry.entry_id]["accessories"] = accessories

    # Forward to media player platform
    await hass.config_entries.async_forward_entry_setups(
        config_entry,
        [
            "media_player",
            "select",
            "number",
            "sensor",
            "binary_sensor",
            "switch",
            "button",
        ],
    )
    return True


def setup(hass: HomeAssistant, config: ConfigEntry) -> bool:
    """Set up the Bose component."""

    async def handle_custom_request(call: ServiceCall) -> None:
        # Extract device_id from target
        ha_device_ids = call.data.get("device_id", [])  # Always returns a list
        if not ha_device_ids:
            raise ValueError("No valid target device provided.")

        ha_device_id = ha_device_ids[
            0
        ]  # Take the first device in case of multiple selections

        resource = call.data["resource"]
        method = call.data["method"]
        body = call.data.get("body", {})

        # Find the matching speaker instance based on Home Assistant device_id
        device_registry = dr.async_get(hass)
        device_entry = device_registry.async_get(ha_device_id)

        if not device_entry:
            raise ValueError(
                f"No device found in Home Assistant for device_id: {ha_device_id}"
            )

        device_registry = dr.async_get(hass)
        speaker = hass.data[DOMAIN][
            device_registry.async_get(ha_device_id).primary_config_entry
        ]["speaker"]

        if not speaker:
            raise ValueError(
                f"No speaker found for Home Assistant device_id: {ha_device_id}"
            )

        try:
            response = await speaker._request(resource, method, body)  # noqa: SLF001
            return {
                "summary": "Successfully sent request to Bose speaker",
                "description": json.dumps(response, indent=2),
            }
        except Exception as e:  # noqa: BLE001
            return {
                "summary": "Failed to send request to Bose speaker",
                "description": str(e),
            }

    hass.services.register(
        DOMAIN,
        "send_custom_request",
        handle_custom_request,
        supports_response=SupportsResponse.ONLY,
    )
    return True


async def registerAccessories(
    hass: HomeAssistant, config_entry, accessories: Accessories
):
    """Register accessories in Home Assistant."""
    device_registry = dr.async_get(hass)
    for accessory in (accessories.subs) + accessories.rears:
        device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers={(DOMAIN, accessory.serialnum)},
            manufacturer="Bose",
            name=accessory.type.replace("_", " "),
            model=accessory.type.replace("_", " "),
            sw_version=accessory.version,
            via_device=(DOMAIN, config_entry.data["guid"]),
        )


async def connect_to_bose(config_entry):
    """Connect to the Bose speaker."""
    data = config_entry.data
    speaker = BoseSpeaker(
        control_token=data["access_token"],
        host=data["ip"],
    )

    try:
        await speaker.connect()
    except Exception as e:  # noqa: BLE001
        logging.error(f"Failed to connect to Bose speaker (IP: {data['ip']}): {e}")  # noqa: G004
        return None

    return speaker
