
"""Config flow for Xiaomi Cloud."""

from collections import OrderedDict
import logging
import time
import traceback

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import (
    async_create_clientsession,
    async_get_clientsession,
)

from .api import browser_find_device_credentials, config_entry_data
from .const import (
    CONF_COORDINATE_TYPE,
    CONF_COORDINATE_TYPE_BAIDU,
    CONF_COORDINATE_TYPE_GOOGLE,
    CONF_COORDINATE_TYPE_ORIGINAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

class XiaomiCloudlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return XiaomiCloudOptionsFlow()

    def __init__(self):
        """Initialize."""
        self._errors = {}
        self.login_result = False
        self._user = None
        self._password = None

    async def async_step_user(self, user_input={}):
        self._errors = {}
        if user_input is not None:
            if user_input.get("manual_input"):
                return await self._show_manual_form()

            existing = await self._check_existing(user_input[CONF_USERNAME])
            if existing:
                return self.async_abort(reason="already_configured")

            self._user = user_input[CONF_USERNAME]
            self._password = user_input[CONF_PASSWORD]

            session = async_create_clientsession(
                self.hass,
                auto_cleanup=False,
                cookie_jar=aiohttp.CookieJar(unsafe=True),
            )

            try:
                credentials = await browser_find_device_credentials(
                    session, self._user, self._password
                )
                if credentials is None:
                    _LOGGER.warning("Xiaomi browser password login failed")
                    self._errors["base"] = "login_url_failed"
                    return await self._show_config_form(user_input)
                self._Service_Token, self.userId = credentials

                if not await self._get_device_info(session):
                    _LOGGER.warning("get_device info Failed")
                    self._errors["base"] = "get_device_failed"
                    return await self._show_config_form(user_input)

                return self.async_create_entry(
                    title=user_input[CONF_USERNAME],
                    data=config_entry_data(
                        self._user,
                        self._password,
                        self._Service_Token,
                        self.userId,
                    ),
                )
            except BaseException as e:
                _LOGGER.warning("Login error: %s", e)
                self._errors["base"] = "login_url_failed"
                return await self._show_config_form(user_input)
            finally:
                session.detach()

        return await self._show_config_form(user_input)


    async def _get_device_info(self, session):
        url = "https://i.mi.com/find/v3/device/status/list"
        headers = {
            "Cookie": f"userId={self.userId};serviceToken={self._Service_Token}",
            "Accept-Language": "zh-CN",
            "Referer": "https://i.mi.com/find",
        }
        try:
            r = await session.get(
                url,
                headers=headers,
                params={"ts": int(time.time() * 1000)},
            )
            if r.status != 200:
                return False

            response = await r.json(content_type=None)
            if response.get("result") != "ok":
                return False
            return response["data"]["deviceList"]
        except (aiohttp.ClientError, KeyError, ValueError):
            _LOGGER.warning(traceback.format_exc())
            return False

    async def _show_config_form(self, user_input, show_manual=False):

        data_schema = OrderedDict()
        data_schema[vol.Required(CONF_USERNAME)] = str
        data_schema[vol.Required(CONF_PASSWORD)] = str
        if show_manual:
            data_schema[vol.Optional("manual_input", default=False)] = bool
        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(data_schema), errors=self._errors
        )

    async def _show_manual_form(self):
        data_schema = vol.Schema({
            vol.Required("serviceToken"): str,
            vol.Required("userId"): str,
        })
        return self.async_show_form(
            step_id="manual", data_schema=data_schema, errors=self._errors
        )

    async def async_step_manual(self, user_input=None):
        self._errors = {}
        if user_input is not None:
            service_token = user_input["serviceToken"]
            user_id = user_input["userId"]

            session = async_get_clientsession(self.hass)
            self._Service_Token = service_token
            self.userId = user_id

            device_info = await self._get_device_info(session)
            if device_info is not False:
                return self.async_create_entry(
                    title=self._user or user_id,
                    data={
                        CONF_USERNAME: self._user or user_id,
                        CONF_PASSWORD: "",
                        "serviceToken": service_token,
                        "userId": user_id,
                        "manual": True,
                    },
                )
            self._errors["base"] = "manual_cookie_invalid"
            return await self._show_manual_form()

        return await self._show_manual_form()

    async def async_step_import(self, user_input):
        """Import a config entry.

        Special type of import, we're not actually going to store any data.
        Instead, we're going to rely on the values that are in config file.
        """
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return self.async_create_entry(title="configuration.yaml", data={})

    async def _check_existing(self, host):
        for entry in self._async_current_entries():
            if host == entry.data.get(CONF_NAME):
                return True


class XiaomiCloudOptionsFlow(config_entries.OptionsFlow):
    """Config flow options for Colorfulclouds."""

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.options.get(CONF_SCAN_INTERVAL, 60),
                    ): int,
                    vol.Optional(
                        CONF_COORDINATE_TYPE,
                        default=self.config_entry.options.get(CONF_COORDINATE_TYPE, CONF_COORDINATE_TYPE_ORIGINAL),
                    ): vol.In([CONF_COORDINATE_TYPE_BAIDU, CONF_COORDINATE_TYPE_GOOGLE, CONF_COORDINATE_TYPE_ORIGINAL])
                }
            ),
        )

