"""Constants for the 北京顺义自来水天然气信息查询 integration."""
import logging
from datetime import timedelta

DOMAIN = "bjsy_water_gas"

PGC_PRICE = [
    {
        "key": "尖峰",
        "month": [7, 8],
        "time_slot": [[11, 13], [16, 17]]
    },
    {
        "key": "峰",
        "time_slot": [[10, 15], [18, 21]]
    },
    {
        "key": "平",
        "time_slot": [[7, 10], [15, 18], [21, 23]]
    },
    {
        "key": "谷",
        "time_slot": [[23, 7]]
    }
]

LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(minutes=10)