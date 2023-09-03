# -*- coding: utf-8 -*-
"""Config flow for 北京顺义自来水天然气信息查询 integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from requests import RequestException

from .const import DOMAIN, LOGGER
from .szjf import SZJFData, InvalidData

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("customerCode"): str,
        vol.Required("cuOpenId"): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.
    """
    session = async_get_clientsession(hass)
    cuOpenId = data["cuOpenId"]
    customerCode = data["customerCode"]
    api: SZJFData
    if cuOpenId and customerCode:

        try:
            api = SZJFData(session, cuOpenId, customerCode)
            await api.async_auth_check()
            await api.async_get_detail(1)
            return data
        except InvalidData as exc:
            LOGGER.error(exc)
            raise InvalidAuth
        except RequestException:
            raise CannotConnect
    else:
        raise InvalidFormat


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    data = None

    async def async_step_user(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title="用户号：" + info["customerCode"], data=info)
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidFormat(HomeAssistantError):
    """Error to indicate there is invalid format."""
