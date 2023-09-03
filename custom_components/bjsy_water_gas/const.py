# -*- coding: utf-8 -*-
"""Constants for the 北京顺义自来水天然气信息查询 integration."""
import logging
from datetime import timedelta

DOMAIN = "bjsy_water_gas"

LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(hours=6)