"""Config flow for Bose integration."""

import logging

from pybose.BoseAuth import BoseAuth
from pybose.BoseDiscovery import BoseDiscovery
from pybose.BoseSpeaker import BoseSpeaker
import voluptuous as vol

from homeassistant import config_entries
import homeassistant.components.zeroconf
from homeassistant.config_entries import ConfigFlowResult

from .const import DOMAIN


class BoseConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bose integration."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the Bose config flow."""
        self.discovered_ips = []  # List to store discovered IPs
        self.mail = None
        self.password = None

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            self.mail = user_input["mail"]
            self.password = user_input["password"]

            if user_input.get("device") == "manual" or not user_input.get("device"):
                # Transition to the manual IP step
                return await self.async_step_manual_ip()

            # User selected a discovered IP
            ip = user_input["device"]
            try:
                return await self._get_device_info(self.mail, self.password, ip)

            except Exception as e:
                logging.exception("Unexpected error", exc_info=e)
                errors["base"] = "auth_failed"

        # Perform discovery to populate the dropdown
        if not self.discovered_ips:
            try:
                self.discovered_ips = await self._discover_devices()
            except Exception as e:
                logging.exception("Discovery failed", exc_info=e)
                self.discovered_ips = []

        # Prepare dropdown options
        ip_options = {ip: ip for ip in self.discovered_ips}
        ip_options["manual"] = "Enter IP Manually"

        # Show the form for input
        data_schema = vol.Schema(
            {
                vol.Required("mail"): str,
                vol.Required("password"): str,
                vol.Required("device", default="manual"): vol.In(ip_options),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "note": (
                    "If your device is not discovered, you can select 'Enter IP Manually' to enter it on the next page."
                )
            },
        )

    async def async_step_manual_ip(self, user_input=None) -> ConfigFlowResult:
        """Handle manual IP entry."""
        errors = {}

        if user_input is not None:
            ip = user_input["manual_ip"]

            try:
                return await self._get_device_info(self.mail, self.password, ip)

            except Exception as e:
                logging.exception("Unexpected error", exc_info=e)
                errors["base"] = "auth_failed"

        # Show the form for manual IP input
        data_schema = vol.Schema(
            {
                vol.Required("manual_ip"): str,
            }
        )

        return self.async_show_form(
            step_id="manual_ip",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "note": (
                    "Enter the IP address of your Bose device manually if it wasn't discovered."
                )
            },
        )

    async def _discover_devices(self):
        """Discover devices using BoseDiscovery in an executor."""
        zeroconf = await homeassistant.components.zeroconf.async_get_instance(self.hass)

        def _run_discovery():
            """Run the blocking discovery method."""
            discovery = BoseDiscovery(zeroconf=zeroconf)
            devices = discovery.discover_devices()
            return [device["IP"] for device in devices]

        return await self.hass.async_add_executor_job(_run_discovery)

    def _get_control_token(self, email, password):
        """Authenticate and retrieve the control token."""
        bose_auth = BoseAuth()
        control_token = bose_auth.getControlToken(email, password, forceNew=True)
        return control_token["refresh_token"]

    async def _get_device_info(self, mail, password, ip):
        """Get the device info."""
        access_token = await self.hass.async_add_executor_job(
            self._get_control_token, self.mail, self.password
        )

        speaker = BoseSpeaker(control_token=access_token, host=ip)
        await speaker.connect()
        system_info = await speaker.get_system_info()

        guid = speaker.get_device_id()

        return self.async_create_entry(
            title=f"{system_info.name} ({ip})",
            data={
                "mail": self.mail,
                "password": self.password,
                "ip": ip,
                "access_token": access_token,
                "guid": guid,
                "serial": system_info.serialNumber,
                "name": system_info.name,
            },
        )
