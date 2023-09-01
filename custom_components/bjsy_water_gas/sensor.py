from homeassistant.components.sensor import (
    SensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, STATE_UNKNOWN, UnitOfVolumeFlowRate
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .const import DOMAIN, UPDATE_INTERVAL, LOGGER
from .szjf import SZJFCorrdinator

SZJF_SENSORS = {
    "balance": {
        "name": "电费余额",
        "icon": "hass:cash-100",
        "unit_of_measurement": "元",
        "attributes": ["last_update"],
    },
    "current_level": {"name": "当前用电阶梯", "icon": "hass:stairs"},
    "current_price": {
        "name": "当前电价",
        "icon": "hass:cash-100",
        "unit_of_measurement": "CNY/kWh",
    },
    "current_level_consume": {
        "name": "当前阶梯用电",
        "device_class": SensorDeviceClass.ENERGY,
        "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
    },
    "current_level_remain": {
        "name": "当前阶梯剩余额度",
        "device_class": SensorDeviceClass.ENERGY,
        "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
    },
    "year_consume": {
        "name": "本年度用电量",
        "device_class": SensorDeviceClass.ENERGY,
        "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
    },
    "year_consume_bill": {
        "name": "本年度电费",
        "icon": "hass:cash-100",
        "unit_of_measurement": "元",
    },
    "current_pgv_type": {"name": "当前电价类别", "icon": "hass:cash-100"},
}


async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
):
    sensors = []
    config = hass.data[DOMAIN][config_entry.entry_id]

    cuOpenId = config.get("cuOpenId")
    customerCode = config.get("customerCode")

    api = SZJFCorrdinator(hass, cuOpenId, customerCode)
    hass.data[DOMAIN]["instance"] = api

    coordinator = DataUpdateCoordinator(
        hass,
        LOGGER,
        name=DOMAIN,
        update_interval=UPDATE_INTERVAL,
        update_method=api.async_update_data,
    )
    LOGGER.info("async_setup_entry: " + str(coordinator))
    await coordinator.async_refresh()
    data = coordinator.data
    sgcc_sensors_keys = SZJF_SENSORS.keys()
    for meterCode, values in data.items():
        for key in sgcc_sensors_keys:
            if key in values.keys():
                sensors.append(SGCCSensor(coordinator, meterCode, key))

        for month in range(12):
            sensors.append(SGCCHistorySensor(coordinator, meterCode, month))
    async_add_entities(sensors, False)
    return None


class SGCCBaseSensor(CoordinatorEntity):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._unique_id = None

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def should_poll(self):
        return False


class SGCCSensor(SGCCBaseSensor):
    def __init__(self, coordinator, meter_code, meter_type, sensor_key):
        super().__init__(coordinator)
        self._meter_code = meter_code
        self._meter_type = meter_type
        self._sensor_key = sensor_key
        self._config = SZJF_SENSORS[self._sensor_key]
        self._attributes = self._config.get("attributes")
        self._coordinator = coordinator
        self._unique_id = f"{DOMAIN}.{meter_code}_{meter_type}_{sensor_key}"
        self.entity_id = self._unique_id

    def get_value(self, attribute=None):
        try:
            if attribute is None:
                return self._coordinator.data.get(self._meter_code).get(self._sensor_key)
            return self._coordinator.data.get(self._meter_code).get(attribute)
        except KeyError:
            return STATE_UNKNOWN

    @property
    def name(self):
        return self._config.get("name")

    @property
    def state(self):
        return self.get_value()

    @property
    def icon(self):
        return self._config.get("icon")

    @property
    def device_class(self):
        return self._config.get("device_class")

    @property
    def unit_of_measurement(self):
        return self._config.get("unit_of_measurement")

    @property
    def extra_state_attributes(self):
        attributes = {}
        if self._attributes is not None:
            try:
                for attribute in self._attributes:
                    attributes[attribute] = self.get_value(attribute)
            except KeyError:
                pass
        return attributes


class SGCCHistorySensor(SGCCBaseSensor):
    def __init__(self, coordinator, meter_code, meter_type, index):
        super().__init__(coordinator)
        self._meter_code = meter_code
        self._meter_type = meter_type
        self._coordinator = coordinator
        self._index = index
        self._unique_id = f"{DOMAIN}.{meter_code}_{meter_type}_history_{index + 1}"
        self.entity_id = self._unique_id

    @property
    def name(self):
        try:
            return (
                self._coordinator.data.get(self._meter_code)
                .get("history")[self._index]
                .get("name")
            )
        except KeyError:
            return STATE_UNKNOWN

    @property
    def state(self):
        try:
            return (
                self._coordinator.data.get(self._meter_code)
                .get("history")[self._index]
                .get("consume")
            )
        except KeyError:
            return STATE_UNKNOWN

    @property
    def extra_state_attributes(self):
        try:
            return {
                "consume_bill": self._coordinator.data.get(self._meter_code)
                .get("history")[self._index]
                .get("consume_bill")
            }
        except KeyError:
            return {"consume_bill": 0.0}

    @property
    def device_class(self):
        if "1" == self._meter_type:
            return SensorDeviceClass.WATER
        if "2" == self._meter_type:
            return SensorDeviceClass.GAS
        return SensorDeviceClass.WATER

    @property
    def unit_of_measurement(self):
        return UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR
