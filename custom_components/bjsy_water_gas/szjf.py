import asyncio
import re

import async_timeout
from bs4 import BeautifulSoup
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import LOGGER

BASE_URL = "https://ys.shunzhengjinfu.com/cis/wechart/$https://ys.shunzhengjinfu.com/cis/wechart/we-chart!"

DETAIL_URL = f'{BASE_URL}customerOverallMeterList.action'
"""查当前户号下水、气信息（余额、用量、阶梯）
"""
METERCODE_URL = "%ssmartWaterMeterList.action" % BASE_URL
"""（表的描述信息更多）（用于获取表号） 查当前户号下水、气信息（余额、用量、阶梯、表号）
"""
BILLINFO_URL = f'{BASE_URL}customerChargeBillChart.action'
"""查最近半年的用量
每次查一个表的半年用量
"""


class SZJFCorrdinator:
    def __init__(self, hass, cu_openid, customer_code):
        self._hass = hass
        session = async_create_clientsession(hass)
        self._szjf = SZJFData(session, cu_openid, customer_code)

    async def async_update_data(self):
        try:
            async with async_timeout.timeout(60):
                data = await self._szjf.async_get_data()
                if not data:
                    raise UpdateFailed("Failed to data update")
                return data
        except asyncio.TimeoutError as ex:
            raise UpdateFailed("Data update timed out") from ex
        except Exception as ex:
            LOGGER.error(
                "Failed to data update with unknown reason: %(ex)s", {"ex": str(ex)}
            )
            raise UpdateFailed("Failed to data update with unknown reason") from ex


class AuthFailed(Exception):
    pass


class InvalidData(Exception):
    pass


class SZJFData:
    def __init__(self, session, cu_openid, customer_code):
        self._session = session
        self._cu_openid = cu_openid
        self._customer_code = customer_code
        self._info = {}

    @staticmethod
    def tuple2list(tup: tuple):
        return {bytes.decode(tup[i][0]): bytes.decode(tup[i][1]) for i, _ in enumerate(tup)}

    @staticmethod
    def common_headers():
        headers = {
            "Host": "ys.shunzhengjinfu.com",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-cn, zh-Hans; q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, "
                          "like Gecko)"
                          "Mobile/15E148 MicroMessenger/8.0.40(0x18002831)"
                          "NetType/WIFI Language/zh_CN",
            "Connection": "keep-alive",
        }
        return headers

    async def async_auth_check(self):
        headers = self.common_headers()
        ret = True
        r = await self._session.get(DETAIL_URL, headers=headers, timeout=10, params={
            "customerCode": self._customer_code,
            "cuOpenId": self._cu_openid,
            "state": "00000001",
            "status": "",
        })
        if r.status == 200:
            html_text = await r.read()
            html_text = str(html_text)

            LOGGER.error(r.status)
            print(html_text)
            if self._customer_code in html_text and "水表" in html_text:
                ret = True
            else:
                ret = False
                LOGGER.error(f"get_detail error: {html_text}")
        else:
            ret = False
            LOGGER.error(f"get_detail response status_code = {r.status_code}")
        return ret

    async def async_get_detail(self, meterUseType):
        headers = self.common_headers()
        ret = True
        r = await self._session.get(METERCODE_URL, headers=headers, timeout=10, params={
            "meterUseType": meterUseType,
            "customerCode": self._customer_code,
            "cuOpenId": self._cu_openid,
            "state": "00000001",
        })
        if r.status == 200:

            html_text = await r.read()
            html_text = str(html_text)
            LOGGER.error(r.status)
            print(html_text)
            if self._customer_code in html_text:
                ret = True
                detail = self.parse_html_detail(html_text)
                for key, v in detail:
                    self._info[key] = v
            else:
                ret = False
                LOGGER.error(f"get_detail error: {html_text}")
        else:
            ret = False
            LOGGER.error(f"get_detail response status_code = {r.status_code}")
        return ret

    async def async_get_monthly_bill(self, meterCode, meterUseType):
        headers = self.common_headers()
        r = await self._session.get(BILLINFO_URL, headers=headers, timeout=10, params={
            "meterCode": meterCode,
            "meterUseType": meterUseType,
            "customerCode": self._customer_code,
        })

        if r.status == 200:
            html_text = await r.read()
            html_text = str(html_text)
            if self._customer_code in html_text:
                ret = True
                monthly = self.parse_html_monthly(html_text)
                self._info[meterCode]["history"] = range(len(monthly))
                for n in range(len(monthly)):
                    self._info[meterCode]["history"][n] = monthly[n]

            else:
                ret = False
                LOGGER.error(f"get_detail error: {html_text}")
        else:
            ret = False
            LOGGER.error(f"get_detail response status_code = {r.status_code}")
        return ret

    def parse_html_detail(self, html_text) -> dict[str, any]:
        soup = BeautifulSoup(html_text, 'html.parser')

        result = {}
        elements = soup.find_all(id=re.compile(r'^detial_water_1_\d'))
        for element in elements:
            print("---------------")
            button = element.select_one('button')
            onclick = button['onclick']
            match = re.search(r"prestoreWaterMoney\('(.*)'\)", onclick)
            meterCode, meterUseType
            if match:
                params = match.group(1).replace("'", "").split(',')
                meterUseType = params[1]
                meterCode = params[2]
            data = {"meterUseType": meterUseType}
            content = element.select_one('.mui-content')
            texts = content.select('a')
            for text in texts:
                print(text)
                if "当前余额" in str(text):
                    balance = str(text.select_one('span').text).strip("(元)")
                    data["balance"] = balance
                if "年累计量" in str(text):
                    print(str(text.select_one('span').text))
                    year_consume = str(text.select_one('span').text).strip("(立方米)")
                    data["year_consume"] = year_consume
                if "当前阶梯" in str(text):
                    print(str(text.select_one('span').text))
                    current_level = str(text.select_one('span').text)
                    data["current_level"] = current_level
            result[meterCode] = data
        return result

    def parse_html_monthly(self, html_text):
        month_re = re.compile(r'xAxisData\.push\(\'(\d{4})-(\d{2})月\'\);')
        amount_re = re.compile(r'amountData\.push\((.*?)\);')
        money_re = re.compile(r'moneyData\.push\((.*?)\);')

        month_arr = month_re.findall(html_text)
        amount_arr = amount_re.findall(html_text)
        money_arr = money_re.findall(html_text)

        data = []
        if len(month_arr) == len(amount_arr) and len(month_arr) == len(money_arr):
            for n in range(len(month_arr)):
                month = month_arr[n]
                amount = amount_arr[n]
                money = money_arr[n]
                data.append({"month": month, "amount": amount, "money": money})
                LOGGER.debug(f'{month[0]}年{month[1]}月 用量: {amount}  金额: {money}')
        data.sort(key=lambda x: x['month'].split('-')[1], reverse=True)
        return data

    async def async_get_data(self):
        await self.async_get_detail(1)
        await self.async_get_detail(2)
        for meterCode in self._info.keys():
            await self.async_get_monthly_bill(meterCode, self._info[meterCode]["meterUseType"])
        LOGGER.debug(f"Data {self._info}")
        return self._info
