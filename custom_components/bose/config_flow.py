"""Config flow for Bose integration."""

from pybose.BoseAuth import BoseAuth
from pybose.BoseDiscovery import BoseDiscovery
from pybose.BoseSpeaker import BoseSpeaker
import voluptuous as vol

from homeassistant import config_entries
import homeassistant.components.zeroconf
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.helpers import translation as translation_helper

from .const import _LOGGER, DOMAIN


async def Discover_Bose_Devices(hass: HomeAssistant):
    """Discover devices using BoseDiscovery in an executor."""
    zeroconf = await homeassistant.components.zeroconf.async_get_instance(hass)

    def _run_discovery():
        """Run the blocking discovery method."""
        discovery = BoseDiscovery(zeroconf=zeroconf)
        devices = discovery.discover_devices(timeout=1)
        return [
            {
                "ip": device["IP"],
                "guid": device["GUID"],
            }
            for device in devices
        ]

    return await hass.async_add_executor_job(_run_discovery)


class BoseConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bose integration."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the Bose config flow."""
        self.discovered_ips = []  # List to store discovered IPs
        self.mail = None
        self.password = None
        self._auth = None

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            self.mail = user_input["mail"]
            self.password = user_input["password"]

            login_response = await self.hass.async_add_executor_job(
                self._login, self.mail, self.password
            )

            if login_response:
                if user_input.get("device") == "manual" or not user_input.get("device"):
                    return await self.async_step_manual_ip()

                # User selected a discovered IP
                ip = user_input["device"]
                try:
                    return await self._get_device_info(self.mail, self.password, ip)
                except Exception as e:  # noqa: BLE001
                    _LOGGER.exception("Unexpected error", exc_info=e)
                    errors["base"] = "auth_failed"
            else:
                errors["base"] = "auth_failed"

        # Perform discovery to populate the dropdown
        if not self.discovered_ips:
            try:
                self.discovered_ips = await self._discover_devices()
            except Exception as e:  # noqa: BLE001
                _LOGGER.exception("Discovery failed", exc_info=e)
                self.discovered_ips = []

        ip_options = {ip: ip for ip in self.discovered_ips}
        try:
            translations = await translation_helper.async_get_translations(
                self.hass, self.hass.config.language, "config", integrations=[DOMAIN]
            )
            manual_label = translations.get(
                f"component.{DOMAIN}.config.step.user.data.manual_ip",
                "Enter IP Manually",
            )
        except (ValueError, RuntimeError):
            manual_label = "Enter IP Manually"

        ip_options["manual"] = manual_label

        # Show the form for input
        data_schema = vol.Schema(
            {
                vol.Required("mail"): str,
                vol.Required("password"): str,
                vol.Required("device", default="manual"): vol.In(ip_options),
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_manual_ip(self, user_input=None) -> ConfigFlowResult:
        """Handle manual IP entry."""
        errors = {}

        if user_input is not None:
            ip = user_input["manual_ip"]

            try:
                return await self._get_device_info(self.mail, self.password, ip)
            except Exception as e:  # noqa: BLE001
                _LOGGER.exception("Unexpected error", exc_info=e)
                errors["base"] = "auth_failed"

        # Show the form for manual IP input
        data_schema = vol.Schema(
            {
                vol.Required("manual_ip"): str,
            }
        )

        try:
            translations = await translation_helper.async_get_translations(
                self.hass, self.hass.config.language, "config", integrations=[DOMAIN]
            )
            manual_note = translations.get(
                f"component.{DOMAIN}.config.step.user.data.manual_ip",
                "Enter the IP address of your Bose device manually if it wasn't discovered.",
            )
        except (ValueError, RuntimeError):
            manual_note = "Enter the IP address of your Bose device manually if it wasn't discovered."

        return self.async_show_form(
            step_id="manual_ip",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={"note": manual_note},
        )

    async def _discover_devices(self):
        """Discover devices using BoseDiscovery in an executor."""
        devices = await Discover_Bose_Devices(self.hass)
        return [device["ip"] for device in devices]

    def _login(self, email, password):
        """Authenticate and retrieve the control token."""
        try:
            self._auth = BoseAuth()
            return self._auth.getControlToken(email, password, forceNew=True)
        except Exception as e:  # noqa: BLE001
            _LOGGER.exception("Failed to get control token", exc_info=e)
            return None

    async def _get_device_info(self, mail, password, ip):
        """Get the device info."""
        try:
            speaker = BoseSpeaker(bose_auth=self._auth, host=ip)  # pyright: ignore[reportArgumentType]
            await speaker.connect()
            system_info = await speaker.get_system_info()
            if not system_info:
                return self.async_abort(reason="info_failed")
        except Exception as e:  # noqa: BLE001
            _LOGGER.exception("Failed to get system info", exc_info=e)
            return self.async_abort(reason="connect_failed")

        guid = speaker.get_device_id()

        if self._auth is None:
            return self.async_abort(reason="auth_failed")

        tokens = self._auth.getCachedToken()

        if (
            tokens is None
            or tokens.get("bosePersonID") is None
            or tokens.get("access_token") is None
            or tokens.get("refresh_token") is None
        ):
            return self.async_abort(reason="auth_failed")

        return self.async_create_entry(
            title=f"{system_info['name']}",
            data={
                "mail": self.mail,
                "password": self.password,
                "ip": ip,
                "bose_person_id": tokens.get("bosePersonID"),
                "access_token": tokens.get("access_token"),
                "refresh_token": tokens.get("refresh_token"),
                "guid": guid,
                "serial": system_info["serialNumber"],
                "name": system_info["name"],
            },
        )
