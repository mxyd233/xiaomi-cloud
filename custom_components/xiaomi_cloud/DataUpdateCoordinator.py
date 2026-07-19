import asyncio
import base64
import datetime
import hashlib
import json
import logging
import time
from urllib import parse

import aiohttp
from aiohttp.client_exceptions import ClientConnectorError
import async_timeout

from homeassistant.helpers.aiohttp_client import (
    async_create_clientsession,
    async_get_clientsession,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    browser_find_device_credentials,
    device_status_params,
    entity_data,
    lost_command_params,
    noise_command_params,
)
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

class XiaomiCloudDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching XiaomiCloud data API."""
    def __init__(
        self,
        hass,
        user,
        password,
        scan_interval,
        coordinate_type,
        service_token=None,
        user_id=None,
        credential_update_callback=None,
    ):
        """Initialize."""
        self._username = user
        self._password = password
        self._headers = {}
        self._cookies = {}
        self._device_info = {}
        self._serviceLoginAuth2_json = {}
        self._sign = None
        self._scan_interval = scan_interval
        self._coordinate_type = coordinate_type
        self.service_data = None
        self.userId = user_id
        self._Service_Token = service_token
        self._manual_mode = bool(service_token and user_id)
        self._credential_update_callback = credential_update_callback
        self.login_result = False
        self.service = None

        update_interval = (
            datetime.timedelta(minutes=self._scan_interval)
        )
        _LOGGER.debug("Data will be update every %s", update_interval)

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=update_interval)

    def _set_credentials(self, service_token, user_id):
        """Store refreshed Find Device credentials."""
        self._Service_Token = service_token
        self.userId = user_id
        self._manual_mode = True
        if self._credential_update_callback is not None:
            self._credential_update_callback(service_token, user_id)

    async def _async_refresh_credentials(self):
        """Refresh Find Device credentials with the stored account password."""
        if not self._username or not self._password:
            return False
        session = async_create_clientsession(
            self.hass,
            auto_cleanup=False,
            cookie_jar=aiohttp.CookieJar(unsafe=True),
        )
        try:
            credentials = await browser_find_device_credentials(
                session, self._username, self._password
            )
        finally:
            session.detach()
        if credentials is None:
            return False
        self._set_credentials(*credentials)
        return True

    async def _async_ensure_device_info(self, session):
        """Load devices, refreshing rejected stored credentials once."""
        if await self._get_device_info(session):
            return True
        if not await self._async_refresh_credentials():
            return False
        return await self._get_device_info(session)

    async def _get_sign(self, session):
        url = 'https://account.xiaomi.com/pass/serviceLogin?sid=i.mi.com&_json=true'
        _device_id = hashlib.md5(b'xiaomi_cloud_ha').hexdigest().upper()[:16]
        self._headers['User-Agent'] = 'Android-7.1.1-1.0.0-ONEPLUS A3010-136-{} APP/xiaomi.smarthome APPV/620301'.format(_device_id)
        _LOGGER.debug("_get_sign headers: %s", self._headers)
        try:
            with async_timeout.timeout(15):
                r = await session.get(url, headers=self._headers)
            text = await r.text()
            if text.startswith('&&&START&&&'):
                text = text[len('&&&START&&&'):]
            resp = json.loads(text)
            self._sign = resp.get('_sign')
            if self._sign:
                _LOGGER.debug("_sign obtained: %s", self._sign[:20])
                return True
            else:
                _LOGGER.warning("No _sign in response: %s", resp)
                return False
        except BaseException as e:
            _LOGGER.warning("get_sign error: %s", e)
            return False

    async def _serviceLoginAuth2(self, session, captCode=None):
        url = 'https://account.xiaomi.com/pass/serviceLoginAuth2'
        self._headers['Content-Type'] = 'application/x-www-form-urlencoded'
        self._headers['Accept'] = '*/*'
        self._headers['Origin'] = 'https://account.xiaomi.com'
        self._headers['Referer'] = 'https://account.xiaomi.com/pass/serviceLogin?sid%3Di.mi.com&sid=i.mi.com&_locale=zh_CN&_snsNone=true'
        _device_id = hashlib.md5(b'xiaomi_cloud_ha').hexdigest().upper()[:16]

        auth_post_data = {'_json': 'true',
                          '_sign': self._sign,
                          'callback': 'https://i.mi.com/sts',
                          'deviceId': _device_id,
                          'hash': hashlib.md5(self._password.encode('utf-8')).hexdigest().upper(),
                          'qs': '?sid=i.mi.com&_json=true',
                          'sdkVersion': '3.8.6',
                          'serviceParam': '{"checkSafePhone":false}',
                          'sid': 'i.mi.com',
                          'user': self._username}
        try:
            if captCode != None:
                url = 'https://account.xiaomi.com/pass/serviceLoginAuth2?_dc={}'.format(
                    int(round(time.time() * 1000)))
                auth_post_data['captCode'] = captCode
                self._headers['Cookie'] = self._headers['Cookie'] + \
                                          '; ick={}'.format(self._cookies['ick'])
            with async_timeout.timeout(15):
                r = await session.post(url, headers=self._headers, data=auth_post_data, cookies=self._cookies)
            text = await r.text()
            if text.startswith('&&&START&&&'):
                text = text[len('&&&START&&&'):]
            self._serviceLoginAuth2_json = json.loads(text)
            _LOGGER.debug('_serviceLoginAuth2 result: code=%s, desc=%s', self._serviceLoginAuth2_json.get('code'), self._serviceLoginAuth2_json.get('description'))
            return True
        except BaseException as e:
            _LOGGER.warning(e.args[0])
            return False

    async def _login_miai(self, session):
        serviceToken = "nonce={}&{}".format(
            self._serviceLoginAuth2_json['nonce'], self._serviceLoginAuth2_json['ssecurity'])
        serviceToken_sha1 = hashlib.sha1(serviceToken.encode('utf-8')).digest()
        base64_serviceToken = base64.b64encode(serviceToken_sha1)
        loginmiai_header = {'User-Agent': 'MISoundBox/1.4.0,iosPassportSDK/iOS-3.2.7 iOS/11.2.5',
                            'Accept-Language': 'zh-cn', 'Connection': 'keep-alive'}
        url = self._serviceLoginAuth2_json['location'] + \
              "&clientSign=" + parse.quote(base64_serviceToken.decode())
        try:
            with async_timeout.timeout(15):
                r = await session.get(url, headers=loginmiai_header)
            if r.status == 200:
                self._Service_Token = r.cookies.get('serviceToken').value
                self.userId = r.cookies.get('userId').value
                _LOGGER.debug("_login_miai",url,"userid",self.userId)

                return True
            else:
                return False
        except BaseException as e:
            _LOGGER.warning(e.args[0])
            return False

    async def _get_device_info(self, session):
        url = "https://i.mi.com/find/v3/device/status/list"
        try:
            async with async_timeout.timeout(15):
                r = await session.get(
                    url,
                    headers=self._find_headers(),
                    params={"ts": self._timestamp()},
                )
            if r.status != 200:
                self.login_result = False
                return False

            response = await r.json(content_type=None)
            if response.get("result") != "ok":
                self.login_result = False
                return False

            self._device_info = response["data"]["deviceList"]
            return True
        except (aiohttp.ClientError, TimeoutError, KeyError, ValueError) as err:
            _LOGGER.warning("Failed to get Xiaomi device list: %s", err)
            return False

    def _find_headers(self):
        return {
            "Cookie": f"userId={self.userId};serviceToken={self._Service_Token}",
            "Accept-Language": "zh-CN",
            "Referer": "https://i.mi.com/find",
        }

    @staticmethod
    def _timestamp():
        return int(time.time() * 1000)

    async def _request_device_status(self, session, device, sync_mode):
        url = "https://i.mi.com/find/v3/device/status"
        params = device_status_params(device, sync_mode, self._timestamp())
        async with async_timeout.timeout(15):
            response = await session.get(
                url,
                headers=self._find_headers(),
                params=params,
            )
        if response.status != 200:
            self.login_result = False
            return None

        result = await response.json(content_type=None)
        if result.get("result") != "ok":
            return None
        return result["data"]

    def _find_targets(self):
        locatable = [
            device
            for device in self._device_info
            if any(
                component.get("online") and 32 in component.get("supportCmds", [])
                for component in device.get("componentList", [])
            )
        ]
        if not self.service_data or not self.service_data.get("imei"):
            return locatable

        identifier = self.service_data["imei"]
        return [
            device
            for device in locatable
            if device.get("fid") == identifier
            or any(
                component.get("did") == identifier
                for component in device.get("componentList", [])
            )
        ]

    async def _send_find_device_command(self, session:aiohttp.ClientSession):
        targets = self._find_targets()
        if not targets:
            return False

        success = True
        for device in targets:
            try:
                result = await self._request_device_status(session, device, 2)
            except (aiohttp.ClientError, TimeoutError, KeyError, ValueError) as err:
                _LOGGER.warning("Failed to locate Xiaomi device: %s", err)
                result = None
            success = result is not None and success
        return success

    def _clear_pending_command(self):
        """Discard a command after one execution attempt."""
        self.service = None
        self.service_data = None
    
    async def _send_noise_command(self, session:aiohttp.ClientSession):
        if self.service_data is None:
            self._clear_pending_command()
            return False
        identifier = self.service_data["imei"]
        device = next(
            (
                item
                for item in self._device_info
                if item.get("fid") == identifier
                or any(
                    component.get("did") == identifier
                    for component in item.get("componentList", [])
                )
            ),
            None,
        )
        if device is None or not (
            data := noise_command_params(device, identifier)
        ):
            _LOGGER.warning("Device does not support play sound: %s", identifier)
            self._clear_pending_command()
            return False
        data["serviceToken"] = self._Service_Token

        url = "https://i.mi.com/find/v2/device/command/send"
        try:
            async with async_timeout.timeout(15):
                response = await session.post(
                    url,
                    headers=self._find_headers(),
                    data=data,
                )
            result = await response.json(content_type=None)
            _LOGGER.debug("noise result: %s", result)
            if response.status == 200 and result.get("result") == "ok":
                self._clear_pending_command()
                return True
            _LOGGER.warning("Failed to play Xiaomi sound: %s", result)
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            _LOGGER.warning("Failed to play Xiaomi sound: %s", err)
        self._clear_pending_command()
        self.login_result = False
        return False

    async def _send_lost_command(self, session:aiohttp.ClientSession):
        if self.service_data is None:
            self._clear_pending_command()
            return False
        identifier = self.service_data["imei"]
        device = next(
            (
                item
                for item in self._device_info
                if item.get("fid") == identifier
                or any(
                    component.get("did") == identifier
                    for component in item.get("componentList", [])
                )
            ),
            None,
        )
        if device is None or not (
            data := lost_command_params(
                device,
                identifier,
                phone=self.service_data["phone"],
                content=self.service_data["content"],
                notify=self.service_data["onlinenotify"],
            )
        ):
            _LOGGER.warning("Device does not support lost mode: %s", identifier)
            self._clear_pending_command()
            return False
        data["serviceToken"] = self._Service_Token

        url = "https://i.mi.com/find/v2/device/command/send"
        try:
            async with async_timeout.timeout(15):
                response = await session.post(
                    url,
                    headers=self._find_headers(),
                    data=data,
                )
            result = await response.json(content_type=None)
            _LOGGER.debug("lost result: %s", result)
            if response.status == 200 and result.get("result") == "ok":
                self._clear_pending_command()
                return True
            _LOGGER.warning("Failed to enable Xiaomi lost mode: %s", result)
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            _LOGGER.warning("Failed to enable Xiaomi lost mode: %s", err)
        self._clear_pending_command()
        self.login_result = False
        return False

    async def _send_clipboard_command(self, session:aiohttp.ClientSession):
        flag = True
        text = self.service_data['text']  
        url = 'https://i.mi.com/clipboard/lite/text'
        _send_clipboard_command_header = {
            'Cookie': 'userId={};serviceToken={}'.format(self.userId, self._Service_Token)}
        data = {'text': text, 'serviceToken': self._Service_Token}
        try:
            with async_timeout.timeout(15):
                r = await session.post(url, headers=_send_clipboard_command_header, data=data)
            _LOGGER.debug("clipboard res: %s", await r.json())    
            if r.status == 200:
                flag = True
                self.service = None
                self.service_data = None
            else:
                flag = False
                self.login_result = False
        except BaseException as e:
            _LOGGER.warning(e.args[0])
            self.login_result = False
            flag = False
        return flag
  
    async def _send_command(self, data):
        self.service_data = data['data']
        self.service = data['service']
        await self.async_refresh()

    async def _get_device_location(self, session:aiohttp.ClientSession):
        devices_info = []
        for device in self._device_info:
            result = None
            try:
                for attempt in range(3):
                    result = await self._request_device_status(session, device, 0)
                    if result is None or not result.get("isLocating"):
                        break
                    if attempt < 2:
                        await asyncio.sleep(3)
            except (aiohttp.ClientError, TimeoutError, KeyError, ValueError) as err:
                _LOGGER.warning("Failed to update Xiaomi device status: %s", err)
                continue
            if result is None:
                continue

            info = entity_data(result, self._coordinate_type)
            if info is not None:
                devices_info.append(info)
        if self.service == "find":
            self.service = None
            self.service_data = None
        return devices_info

    async def _async_update_data(self):
        """Update data via library."""
        _LOGGER.debug("service: %s", self.service)
        tmp = None
        try:
            session = async_get_clientsession(self.hass)
            if self.login_result is True:
                if self.service == "noise":
                    tmp = await self._send_noise_command(session)
                elif self.service == 'lost':
                    tmp = await self._send_lost_command(session)
                elif self.service == 'clipboard':
                    tmp = await self._send_clipboard_command(session)
                elif self._scan_interval>0:
                    tmp = await self._send_find_device_command(session)
                if tmp is True:
                    await asyncio.sleep(15)
                    tmp = await self._get_device_location(session)
                    if not tmp:
                        _LOGGER.info("_get_device_location0 Failed")
                    else:
                        _LOGGER.info("_get_device_location0 succeed")
                else:
                    _LOGGER.info("send_command Failed")
            else:
                if self._scan_interval>0:
                    tmp = await self._async_ensure_device_info(session)
                    if not tmp:
                        _LOGGER.warning('Stored credentials and password refresh failed')
                    else:
                        _LOGGER.info("get_device info succeed")
                        self.login_result = True
                        if self.service == "noise":
                            tmp = await self._send_noise_command(session)
                        elif self.service == 'lost':
                            tmp = await self._send_lost_command(session)
                        elif self.service == 'clipboard':
                            tmp = await self._send_clipboard_command(session)
                        else:
                            tmp = await self._send_find_device_command(session)
                        if tmp is True:
                            await asyncio.sleep(5)
                            tmp = await self._get_device_location(session)
                            if not tmp:
                                _LOGGER.info("_get_device_location1 Failed")
                            else:
                                _LOGGER.info("_get_device_location1 succeed")
                        else:
                            _LOGGER.info("send_command Failed")

        except (
            ClientConnectorError
        ) as error:
            raise UpdateFailed(error)
        if not tmp:
            raise UpdateFailed("Failed to update Xiaomi Cloud location")
        return tmp
