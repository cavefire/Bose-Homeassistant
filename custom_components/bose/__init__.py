"""The Bose component."""

import json
import logging
import asyncio

from pybose.BoseAuth import BoseAuth
from pybose.BoseResponse import Accessories, NetworkStateEnum
from pybose.BoseSpeaker import BoseSpeaker, BoseRequestException

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

    if (
        config_entry.data.get("access_token") is not None
        and config_entry.data.get("refresh_token") is not None
    ):
        # Using existing access token
        logging.debug("Using existing access token for %s", config_entry.data["mail"])
        auth.set_access_token(
            config_entry.data["access_token"],
            config_entry.data["refresh_token"],
            config_entry.data["bose_person_id"],
        )
    else:
        logging.debug("No access token found, logging in with credentials")

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

    hass.async_create_background_task(
        refresh_token_thread(hass, config_entry, auth), "Refresh token"
    )

    speaker = await connect_to_bose(hass, config_entry, auth)

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
        speaker = await connect_to_bose(hass, config_entry, auth)

    system_info = await speaker.get_system_info()
    capabilities = await speaker.get_capabilities()

    await speaker.subscribe()

    # Register device in Home Assistant
    device_registry = dr.async_get(hass)

    identifiers = {(DOMAIN, config_entry.data["guid"])}

    if speaker.has_capability("/network/status"):
        network_status = await speaker.get_network_status()

        for interface in network_status.get("interfaces", []):
            if interface.get("state", NetworkStateEnum.DOWN) == NetworkStateEnum.UP:
                identifiers.add(
                    (
                        DOMAIN,
                        ":".join(
                            interface.get("macAddress")[i : i + 2]
                            for i in range(0, 12, 2)
                        ),
                    )
                )

    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers=identifiers,
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


async def refresh_token_thread(
    hass: HomeAssistant, config_entry: ConfigEntry, auth: BoseAuth
):
    """Refresh the token periodically."""
    while True:
        timeToSleep = auth.get_token_validity_time() * 0.8
        if timeToSleep > 3600:
            logging.debug("Sleeping for %s seconds", timeToSleep)
            await asyncio.sleep(timeToSleep)
        logging.warning("Refreshing token for %s", config_entry.data["mail"])
        if not await refresh_token(hass, config_entry, auth):
            logging.warning(
                "Failed to refresh token for %s. Trying again in 120 seconds",
                config_entry.data["mail"],
            )
            await asyncio.sleep(120)


async def refresh_token(hass: HomeAssistant, config_entry: ConfigEntry, auth: BoseAuth):
    """Refresh the token."""
    try:
        new_token = await hass.async_add_executor_job(auth.do_token_refresh)
        if new_token:
            hass.config_entries.async_update_entry(
                config_entry,
                data={
                    **config_entry.data,
                    "access_token": new_token["access_token"],
                    "refresh_token": new_token["refresh_token"],
                },
            )
            auth.set_access_token(
                new_token["access_token"],
                new_token["refresh_token"],
                config_entry.data["bose_person_id"],
            )
    except Exception as e:  # noqa: BLE001
        logging.error(
            "Failed to refresh token for %s: %s", config_entry.data["mail"], str(e)
        )
        return False
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Unsubscribe from the speaker
    speaker: BoseSpeaker = hass.data[DOMAIN][config_entry.entry_id]["speaker"]
    if speaker:
        await speaker.disconnect()

    # Remove the speaker object from hass.data
    hass.data[DOMAIN].pop(config_entry.entry_id, None)

    # Unload the config entry
    await hass.config_entries.async_unload(config_entry.entry_id)
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
    for accessory in (accessories.get("subs", [])) + accessories.get("rears", {}):
        device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers={(DOMAIN, accessory.get("serialnum", "N/A"))},
            manufacturer="Bose",
            name=accessory.get("type", "").replace("_", " "),
            model=accessory.get("type", "").replace("_", " "),
            sw_version=accessory.get("version", "N/A"),
            via_device=(DOMAIN, config_entry.data["guid"]),
        )


async def connect_to_bose(
    hass: HomeAssistant, config_entry: ConfigEntry, auth: BoseAuth
):
    """Connect to the Bose speaker."""
    data = config_entry.data

    def handle_exception(exception: Exception) -> None:
        """Handle exceptions."""
        if isinstance(exception, BoseRequestException):
            if exception.http_status == 401 and exception.error_status == "0":
                logging.error("Token is invalid or expired. Renewing token!")
                refresh_token(hass, config_entry, auth)

    speaker = BoseSpeaker(
        host=data["ip"],
        bose_auth=auth,
        on_exception=handle_exception,
    )

    try:
        await speaker.connect()
    except Exception as e:  # noqa: BLE001
        logging.error(f"Failed to connect to Bose speaker (IP: {data['ip']}): {e}")  # noqa: G004
        return None

    return speaker
