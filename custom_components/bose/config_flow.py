"""Config flow for Bose integration."""

from typing import Any

from pybose.BoseAuth import BoseAuth
from pybose.BoseDiscovery import BoseDiscovery
from pybose.BoseSpeaker import BoseSpeaker
import voluptuous as vol

from homeassistant import config_entries
import homeassistant.components.zeroconf
from homeassistant.config_entries import ConfigFlowResult, OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector, translation as translation_helper
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

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
        self._discovered_device = None
        self._reauth_entry = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlow:
        """Get the options flow for this handler."""
        return BoseOptionsFlowHandler(config_entry)

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
            _LOGGER.debug("Starting login process for %s", email)
            self._auth = BoseAuth()
            result = self._auth.getControlToken(email, password, forceNew=True)
        except Exception:
            _LOGGER.exception("Failed to get control token for %s", email)
            return None
        else:
            _LOGGER.info("Login successful for %s", email)
            _LOGGER.debug(
                "Login result keys: %s", list(result.keys()) if result else None
            )
            return result

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

        await self.async_set_unique_id(guid)
        self._abort_if_unique_id_configured()

        if self._auth is None:
            return self.async_abort(reason="auth_failed")

        tokens = self._auth.getCachedToken()
        azure_refresh_token = self._auth.get_azure_refresh_token()

        _LOGGER.debug(
            "Cached token keys from initial setup: %s",
            list(tokens.keys()) if tokens else None,
        )

        # Check for both possible key names (API inconsistency)
        bose_person_id = (
            tokens.get("bosePersonID") or tokens.get("bose_person_id")
            if tokens
            else None
        )

        if (
            tokens is None
            or bose_person_id is None
            or tokens.get("access_token") is None
            or tokens.get("refresh_token") is None
            or azure_refresh_token is None
        ):
            _LOGGER.error(
                "Token validation failed during initial setup - bose_person_id: %s, has_access: %s, has_refresh: %s, has_azure_refresh: %s",
                bose_person_id is not None,
                tokens.get("access_token") is not None if tokens else False,
                tokens.get("refresh_token") is not None if tokens else False,
                azure_refresh_token is not None,
            )
            return self.async_abort(reason="auth_failed")

        return self.async_create_entry(
            title=f"{system_info['name']}",
            data={
                "mail": self.mail,
                "ip": ip,
                "bose_person_id": bose_person_id,
                "access_token": tokens.get("access_token"),
                "refresh_token": tokens.get("refresh_token"),
                "azure_refresh_token": azure_refresh_token,
                "guid": guid,
                "serial": system_info["serialNumber"],
                "name": system_info["name"],
            },
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        _LOGGER.debug("Zeroconf discovery info: %s", discovery_info)

        guid = discovery_info.properties.get("GUID")
        if not guid:
            return self.async_abort(reason="no_guid")

        await self.async_set_unique_id(guid)
        self._abort_if_unique_id_configured(updates={"ip": discovery_info.host})

        self._discovered_device = {
            "ip": discovery_info.host,
            "guid": guid,
            "name": discovery_info.name.split(".")[0],
        }

        self.context["title_placeholders"] = {"name": self._discovered_device["name"]}

        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(self, user_input=None) -> ConfigFlowResult:
        """Handle zeroconf confirmation step."""
        errors = {}

        if user_input is not None:
            self.mail = user_input["mail"]
            self.password = user_input["password"]

            login_response = await self.hass.async_add_executor_job(
                self._login, self.mail, self.password
            )

            if login_response:
                try:
                    return await self._get_device_info(
                        self.mail, self.password, self._discovered_device["ip"]
                    )
                except Exception as e:  # noqa: BLE001
                    _LOGGER.exception("Unexpected error", exc_info=e)
                    errors["base"] = "auth_failed"
            else:
                errors["base"] = "auth_failed"

        data_schema = vol.Schema(
            {
                vol.Required("mail"): str,
                vol.Required("password"): str,
            }
        )

        return self.async_show_form(
            step_id="zeroconf_confirm",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "name": self._discovered_device["name"],
                "ip": self._discovered_device["ip"],
            },
        )

    async def async_step_reauth(self, entry_data) -> ConfigFlowResult:
        """Handle reauthentication request."""
        _LOGGER.info("Starting reauthentication flow")
        entry_id = self.context.get("entry_id")
        _LOGGER.debug("Reauth entry_id from context: %s", entry_id)
        if entry_id:
            self._reauth_entry = self.hass.config_entries.async_get_entry(entry_id)
            if self._reauth_entry:
                _LOGGER.info(
                    "Reauthentication for device: %s (mail: %s)",
                    self._reauth_entry.data.get("name"),
                    self._reauth_entry.data.get("mail"),
                )
            else:
                _LOGGER.error("Could not find config entry with id: %s", entry_id)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None) -> ConfigFlowResult:
        """Handle reauthentication confirmation."""
        errors = {}

        if self._reauth_entry is None:
            _LOGGER.error("Reauth entry is None, aborting")
            return self.async_abort(reason="reauth_failed")

        if user_input is not None:
            mail = user_input["mail"]
            password = user_input["password"]
            _LOGGER.info("Attempting reauth login for mail: %s", mail)

            login_response = await self.hass.async_add_executor_job(
                self._login, mail, password
            )
            _LOGGER.debug("Login response received: %s", login_response is not None)

            if login_response and self._auth is not None:
                _LOGGER.debug("Login successful, retrieving cached tokens")
                tokens = self._auth.getCachedToken()
                azure_refresh_token = self._auth.get_azure_refresh_token()

                _LOGGER.debug(
                    "Cached token keys: %s", list(tokens.keys()) if tokens else None
                )
                _LOGGER.debug(
                    "Cached tokens retrieved: %s",
                    {
                        "has_tokens": tokens is not None,
                        "has_bosePersonID": tokens.get("bosePersonID") is not None
                        if tokens
                        else False,
                        "has_bose_person_id": tokens.get("bose_person_id") is not None
                        if tokens
                        else False,
                        "has_access_token": tokens.get("access_token") is not None
                        if tokens
                        else False,
                        "has_refresh_token": tokens.get("refresh_token") is not None
                        if tokens
                        else False,
                        "has_azure_refresh_token": azure_refresh_token is not None,
                    },
                )

                # Check for both possible key names
                bose_person_id = (
                    tokens.get("bosePersonID") or tokens.get("bose_person_id")
                    if tokens
                    else None
                )

                if (
                    tokens is None
                    or bose_person_id is None
                    or tokens.get("access_token") is None
                    or tokens.get("refresh_token") is None
                    or azure_refresh_token is None
                ):
                    _LOGGER.error("Token validation failed - missing required tokens")
                    errors["base"] = "auth_failed"
                else:
                    old_person_id = self._reauth_entry.data.get("bose_person_id")
                    new_person_id = bose_person_id
                    _LOGGER.debug(
                        "Comparing person IDs - old: %s, new: %s",
                        old_person_id,
                        new_person_id,
                    )

                    if old_person_id and new_person_id != old_person_id:
                        _LOGGER.warning(
                            "Account mismatch - old: %s, new: %s",
                            old_person_id,
                            new_person_id,
                        )
                        return self.async_abort(reason="wrong_account")

                    _LOGGER.info("Reauthentication successful, updating config entry")
                    return self.async_update_reload_and_abort(
                        self._reauth_entry,
                        data={
                            **self._reauth_entry.data,
                            "mail": mail,
                            "access_token": tokens.get("access_token"),
                            "refresh_token": tokens.get("refresh_token"),
                            "azure_refresh_token": azure_refresh_token,
                            "bose_person_id": bose_person_id,
                        },
                    )
            else:
                _LOGGER.error(
                    "Login failed - response: %s, auth: %s",
                    login_response is not None,
                    self._auth is not None,
                )
                errors["base"] = "auth_failed"

        data_schema = vol.Schema(
            {
                vol.Required("mail", default=self._reauth_entry.data.get("mail")): str,
                vol.Required("password"): str,
            }
        )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "device_name": self._reauth_entry.data.get("name", "Bose Device"),
            },
        )


class BoseOptionsFlowHandler(OptionsFlow):
    """Handle options flow for the Bose integration."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._original_sources: list[str] = []
        self._selected_source: str | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select which source to configure."""
        if user_input is not None:
            self._selected_source = user_input["source"]
            return await self.async_step_configure_source()

        try:
            media_player = self.hass.data[DOMAIN]["media_entities"].get(
                self.config_entry.data.get("guid")
            )

            if media_player:
                self._original_sources = media_player.get_original_sources()
            else:
                _LOGGER.warning("Media player not found for options flow")
                self._original_sources = []

        except (KeyError, AttributeError) as err:
            _LOGGER.error("Failed to get available sources: %s", err)
            self._original_sources = []

        filtered_sources = [
            source
            for source in self._original_sources
            if not source.startswith("Bluetooth:")
            and source != "Chromecast built-in"
            and not source.startswith("Spotify:")
        ]

        if not filtered_sources:
            return self.async_abort(reason="no_sources_available")

        current_options = self.config_entry.options
        source_options = {}
        for source in filtered_sources:
            rename_key = f"rename_{source.replace(' ', '_').replace(':', '_')}"
            custom_name = current_options.get(rename_key)
            if custom_name:
                display_name = f"{source} ({custom_name})"
            else:
                display_name = source
            source_options[source] = display_name

        data_schema = vol.Schema(
            {
                vol.Required("source"): vol.In(source_options),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
        )

    async def async_step_configure_source(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure rename and linked media player for selected source."""
        if not self._selected_source:
            return await self.async_step_init()

        if user_input is not None:
            current_options = dict(self.config_entry.options)

            source_key = f"linked_player_{self._selected_source.replace(' ', '_').replace(':', '_')}"
            rename_key = (
                f"rename_{self._selected_source.replace(' ', '_').replace(':', '_')}"
            )

            if user_input.get("rename"):
                current_options[rename_key] = user_input["rename"]
            elif rename_key in current_options:
                del current_options[rename_key]

            if user_input.get("linked_player"):
                current_options[source_key] = user_input["linked_player"]
            elif source_key in current_options:
                del current_options[source_key]

            return self.async_create_entry(title="", data=current_options)

        current_options = self.config_entry.options
        source_key = (
            f"linked_player_{self._selected_source.replace(' ', '_').replace(':', '_')}"
        )
        rename_key = (
            f"rename_{self._selected_source.replace(' ', '_').replace(':', '_')}"
        )

        current_linked_value = current_options.get(source_key)
        current_rename_value = current_options.get(rename_key, "")

        data_schema = vol.Schema(
            {
                vol.Optional(
                    "rename",
                    description={"suggested_value": current_rename_value},
                ): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.TEXT,
                    )
                ),
                vol.Optional(
                    "linked_player",
                    description={"suggested_value": current_linked_value},
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="media_player",
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="configure_source",
            data_schema=data_schema,
            description_placeholders={"source_name": self._selected_source},
        )
