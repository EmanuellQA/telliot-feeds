import os

from dataclasses import dataclass
from dataclasses import field
from typing import Any

from telliot_feeds.dtypes.datapoint import datetime_now_utc
from telliot_feeds.dtypes.datapoint import OptionalDataPoint
from telliot_feeds.pricing.price_service import WebPriceService
from telliot_feeds.pricing.price_source import PriceSource
from telliot_feeds.utils.log import get_logger


logger = get_logger(__name__)

class LaunchSpotPriceService(WebPriceService):
    """Launch Price Service"""

    def __init__(self, **kwargs: Any) -> None:
        kwargs["name"] = "Launch Price Service"
        kwargs["url"] = os.getenv("COINGECKO_MOCK_URL", "https://api.coingecko.com/api/v3")
        super().__init__(**kwargs)

    async def get_price(self, asset: str, currency: str) -> OptionalDataPoint[float]:
        """Implement PriceServiceInterface

        This implementation launchs the price of 0.001 for asset and currency.
        """
        return 0.001, datetime_now_utc()

@dataclass
class LaunchpriceSource(PriceSource):
    asset: str = ""
    currency: str = ""
    service: LaunchSpotPriceService = field(default_factory=LaunchSpotPriceService, init=False)