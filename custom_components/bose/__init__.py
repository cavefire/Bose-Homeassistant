"""The Bose component."""

import asyncio
import json

from pybose.BoseAuth import BoseAuth
from pybose.BoseResponse import Accessories, NetworkStateEnum
from pybose.BoseSpeaker import BoseSpeaker

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import ConfigEntryAuthFailed, ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr

from . import config_flow
from .const import _LOGGER, DOMAIN, TOKEN_REFRESH_DELAY, TOKEN_RETRY_DELAY
from .coordinator import BoseCoordinator

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
        and config_entry.data.get("bose_person_id") is not None
        and config_entry.data.get("azure_refresh_token") is not None
    ):
        # Using existing access token
        _LOGGER.debug("Using existing access token for %s", config_entry.data["mail"])
        auth.set_access_token(
            config_entry.data["access_token"],
            config_entry.data["refresh_token"],
            config_entry.data["bose_person_id"],
        )
        # Set Azure refresh token which is required for token refresh
        auth.set_azure_refresh_token(config_entry.data["azure_refresh_token"])
    else:
        # Missing tokens - trigger reauthentication
        _LOGGER.warning(
            "Missing authentication tokens for %s, triggering reauthentication",
            config_entry.data.get("mail"),
        )
        raise ConfigEntryAuthFailed(
            f"Authentication required for {config_entry.data.get('mail')}"
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
                _LOGGER.error(
                    "Found device with same GUID, updating IP to: %s", device["ip"]
                )
                hass.config_entries.async_update_entry(
                    config_entry,
                    data={**config_entry.data, "ip": device["ip"]},
                )
                found = True
                break

        if not found:
            _LOGGER.error(
                "Failed to connect to Bose speaker. No new ip was found, so assuming the device is offline"
            )
            return False

        new_entry = hass.config_entries.async_get_entry(config_entry.entry_id)
        if new_entry is None:
            _LOGGER.error("Config entry not found after updating IP, aborting setup")
            return False
        config_entry = new_entry
        speaker = await connect_to_bose(hass, config_entry, auth)

    if speaker is None:
        _LOGGER.error("Speaker object is None, cannot retrieve system info")
        return False

    system_info = await speaker.get_system_info()
    capabilities = await speaker.get_capabilities()

    await speaker.subscribe()

    # Register device in Home Assistant
    device_registry = dr.async_get(hass)

    identifiers = {(DOMAIN, config_entry.data["guid"])}
    connections = set()

    if speaker.has_capability("/network/status"):
        network_status = await speaker.get_network_status()

        primary_name = network_status.get("primary")
        for interface in network_status.get("interfaces", []):
            if (
                interface.get("type") == primary_name
                and interface.get("state", NetworkStateEnum.DOWN) == NetworkStateEnum.UP
            ):
                mac_address = interface.get("macAddress", "")
                if mac_address:
                    formatted_mac = dr.format_mac(mac_address)
                    connections.add((dr.CONNECTION_NETWORK_MAC, formatted_mac))
                break

    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers=identifiers,
        connections=connections,
        manufacturer="Bose",
        name=system_info["name"],
        model=system_info["productName"],
        serial_number=system_info["serialNumber"],
        sw_version=system_info["softwareVersion"],
    )

    # Store the speaker object separately
    hass.data[DOMAIN][config_entry.entry_id]["speaker"] = speaker
    hass.data[DOMAIN][config_entry.entry_id]["system_info"] = system_info
    hass.data[DOMAIN][config_entry.entry_id]["capabilities"] = capabilities
    hass.data[DOMAIN][config_entry.entry_id]["auth"] = auth

    coordinator = BoseCoordinator(
        hass,
        speaker,
        config_entry.data["guid"],
    )
    hass.data[DOMAIN][config_entry.entry_id]["coordinator"] = coordinator
    await coordinator.async_config_entry_first_refresh()

    try:
        # Not all Devices have accessories like "Bose Portable Smart Speaker"
        accessories = await speaker.get_accessories()
        await registerAccessories(hass, config_entry, accessories)
    except Exception:  # noqa: BLE001
        accessories = []
    hass.data[DOMAIN][config_entry.entry_id]["accessories"] = accessories

    hass.async_create_background_task(
        reconnection_monitor(hass, config_entry, auth),
        "Bose reconnection monitor",
    )

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
        if (
            auth.get_token_validity_time() > 2 * TOKEN_REFRESH_DELAY
        ):  # when token is valid for more than 2 * refresh-delay ...
            _LOGGER.debug(
                "Sleeping for %s seconds before refreshing", TOKEN_REFRESH_DELAY
            )  # wait for 1 x refresh-delay before checking again
            await asyncio.sleep(TOKEN_REFRESH_DELAY)
        _LOGGER.info("Refreshing token for %s", config_entry.data["mail"])
        try:
            if not await refresh_token(hass, config_entry, auth):
                _LOGGER.error(
                    "Failed to refresh token for %s. Trying again in %s seconds",
                    config_entry.data["mail"],
                    TOKEN_RETRY_DELAY,
                )
            else:
                _LOGGER.info(
                    "Token refreshed successfully for %s. New token valid for %s seconds",
                    config_entry.data["mail"],
                    auth.get_token_validity_time(),
                )
        except ConfigEntryAuthFailed:
            # Token refresh failed due to authentication issue - trigger reauth flow
            _LOGGER.warning(
                "Authentication failed for %s, starting reauthentication flow",
                config_entry.data["mail"],
            )
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": "reauth", "entry_id": config_entry.entry_id},
                    data=config_entry.data,
                )
            )
            # Stop the refresh loop after triggering reauth
            break
        await asyncio.sleep(TOKEN_RETRY_DELAY)


async def refresh_token(hass: HomeAssistant, config_entry: ConfigEntry, auth: BoseAuth):
    """Refresh the token."""
    try:
        new_token = await hass.async_add_executor_job(auth.do_token_refresh)
        if new_token:
            # Get the updated Azure refresh token from auth object
            azure_refresh_token = auth.get_azure_refresh_token()

            update_data = {
                **config_entry.data,
                "access_token": new_token["access_token"],
                "refresh_token": new_token["refresh_token"],
            }

            # Update Azure refresh token if available
            if azure_refresh_token:
                update_data["azure_refresh_token"] = azure_refresh_token

            hass.config_entries.async_update_entry(
                config_entry,
                data=update_data,
            )
            _LOGGER.info(
                "Token is valid for %s seconds", auth.get_token_validity_time()
            )
            return True
    except Exception as e:
        error_msg = str(e)
        _LOGGER.error(
            "Failed to refresh token for %s: %s", config_entry.data["mail"], error_msg
        )

        # Check if this is an authentication error that requires reauthentication
        if "refresh token" in error_msg.lower() or "azure" in error_msg.lower():
            _LOGGER.warning(
                "Refresh token invalid for %s, triggering reauthentication flow",
                config_entry.data["mail"],
            )
            raise ConfigEntryAuthFailed(
                f"Refresh token invalid for {config_entry.data['mail']}"
            ) from e
    return False


async def reconnection_monitor(
    hass: HomeAssistant, config_entry: ConfigEntry, auth: BoseAuth
):
    """Monitor speaker connection and attempt reconnection via mDNS if offline."""
    CHECK_INTERVAL = 30
    RECONNECT_DELAY = 10

    while True:
        await asyncio.sleep(CHECK_INTERVAL)

        if not hass.config_entries.async_get_entry(config_entry.entry_id):
            _LOGGER.debug("Config entry removed, stopping reconnection monitor")
            break

        speaker = hass.data[DOMAIN].get(config_entry.entry_id, {}).get("speaker")
        if not speaker:
            _LOGGER.debug("Speaker object not found, stopping reconnection monitor")
            break

        if not speaker.is_connected():
            _LOGGER.warning(
                "Speaker %s is disconnected, attempting reconnection via mDNS discovery",
                config_entry.data.get("guid"),
            )

            await asyncio.sleep(RECONNECT_DELAY)

            try:
                discovered = await config_flow.Discover_Bose_Devices(hass)
                found = False

                for device in discovered:
                    if device["guid"] == config_entry.data["guid"]:
                        current_ip = config_entry.data.get("ip")
                        new_ip = device["ip"]

                        if current_ip != new_ip:
                            _LOGGER.info(
                                "Device %s found with new IP %s (was %s), updating configuration",
                                config_entry.data["guid"],
                                new_ip,
                                current_ip,
                            )
                            hass.config_entries.async_update_entry(
                                config_entry,
                                data={**config_entry.data, "ip": new_ip},
                            )
                        else:
                            _LOGGER.info(
                                "Device %s found at same IP %s, attempting reconnection",
                                config_entry.data["guid"],
                                current_ip,
                            )

                        new_speaker = await connect_to_bose(
                            hass,
                            hass.config_entries.async_get_entry(config_entry.entry_id)
                            or config_entry,
                            auth,
                        )

                        if new_speaker:
                            try:
                                await speaker.disconnect()
                            except Exception:  # noqa: BLE001
                                pass

                            hass.data[DOMAIN][config_entry.entry_id][
                                "speaker"
                            ] = new_speaker
                            coordinator = hass.data[DOMAIN][config_entry.entry_id].get(
                                "coordinator"
                            )
                            if coordinator:
                                coordinator.speaker = new_speaker
                                new_speaker.attach_receiver(
                                    coordinator._cache_message  # noqa: SLF001
                                )

                            await new_speaker.subscribe()

                            _LOGGER.info(
                                "Successfully reconnected to device %s at %s",
                                config_entry.data["guid"],
                                device["ip"],
                            )
                            found = True
                        break

                if not found:
                    _LOGGER.warning(
                        "Device %s not found via mDNS discovery, will retry",
                        config_entry.data["guid"],
                    )

            except Exception:  # noqa: BLE001
                _LOGGER.exception(
                    "Error during reconnection attempt for %s",
                    config_entry.data["guid"],
                )


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Disconnect from the speaker
    speaker: BoseSpeaker = hass.data[DOMAIN][config_entry.entry_id].get("speaker")
    if speaker:
        await speaker.disconnect()

    # Remove our stored data
    hass.data[DOMAIN].pop(config_entry.entry_id, None)

    # Unload each platform we originally set up
    platforms = [
        "media_player",
        "select",
        "number",
        "sensor",
        "binary_sensor",
        "switch",
        "button",
    ]
    unload_ok = True
    for platform in platforms:
        ok = await hass.config_entries.async_forward_entry_unload(
            config_entry, platform
        )
        unload_ok = unload_ok and ok

    return unload_ok


def setup(hass: HomeAssistant, config: ConfigEntry) -> bool:
    """Set up the Bose component."""

    async def handle_custom_request(call: ServiceCall) -> ServiceResponse:
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
        device_entry = device_registry.async_get(ha_device_id)
        if device_entry is None or device_entry.primary_config_entry is None:
            raise ValueError(
                f"No valid config entry found for Home Assistant device_id: {ha_device_id}"
            )
        speaker = hass.data[DOMAIN][device_entry.primary_config_entry]["speaker"]

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

    async def handle_remove_bluetooth_device(call: ServiceCall) -> None:
        """Handle remove Bluetooth device service call."""
        ha_device_id = call.data["device_id"]
        mac_address = call.data["mac_address"]

        # Find the matching speaker instance
        device_registry = dr.async_get(hass)
        device_entry = device_registry.async_get(ha_device_id)
        if device_entry is None or device_entry.primary_config_entry is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="config_entry_not_found",
                translation_placeholders={"device_id": ha_device_id},
            )
        speaker = hass.data[DOMAIN][device_entry.primary_config_entry]["speaker"]

        if not speaker:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="speaker_not_found",
                translation_placeholders={"device_id": ha_device_id},
            )

        await speaker.remove_bluetooth_sink_device(mac_address)

    hass.services.register(
        DOMAIN,
        "remove_bluetooth_device",
        handle_remove_bluetooth_device,
    )
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

    subs = accessories.get("subs") or []
    rears_raw = accessories.get("rears") or []

    rears: list = []
    if isinstance(rears_raw, dict):
        for v in rears_raw.values():
            if isinstance(v, list):
                rears.extend(v)
            else:
                rears.append(v)
    elif isinstance(rears_raw, list):
        rears = list(rears_raw)
    else:
        rears = [rears_raw]

    for accessory in list(subs) + rears:
        device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers={(DOMAIN, accessory.get("serialnum", "N/A"))},
            serial_number=accessory.get("serialnum", "N/A"),
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

    speaker = BoseSpeaker(host=data["ip"], bose_auth=auth)

    try:
        await speaker.connect()
    except Exception as e:  # noqa: BLE001
        _LOGGER.error("Failed to connect to Bose speaker (IP: %s): %s", data["ip"], e)
        return None

    return speaker
