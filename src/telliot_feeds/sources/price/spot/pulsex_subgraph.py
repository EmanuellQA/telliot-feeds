import os

from dataclasses import dataclass
from dataclasses import field
from typing import Any

import requests

from telliot_feeds.dtypes.datapoint import datetime_now_utc
from telliot_feeds.dtypes.datapoint import OptionalDataPoint
from telliot_feeds.pricing.price_service import WebPriceService
from telliot_feeds.pricing.price_source import PriceSource
from telliot_feeds.utils.log import get_logger

logger = get_logger(__name__)
pulsex_subgraph_supporten_tokens = {
    "dai": "0x826e4e896cc2f5b371cd7bb0bd929db3e3db67c0",
    "usdc": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
    "plsx": "0x8a810ea8b121d08342e9e7696f4a9915cbe494b7",
    "fetch": os.getenv("FETCH_ADDRESS")
}


class PulseXSupgraphService(WebPriceService):
    """PulseX Subgraph Price Service for token price"""

    def __init__(self, **kwargs: Any) -> None:
        kwargs["name"] = "PulseX Supgraph Price Service"
        kwargs["url"] = os.getenv("PULSEX_SUBGRAPH_URL")
        kwargs["timeout"] = 10.0
        super().__init__(**kwargs)

    async def get_price(self, asset: str, currency: str) -> OptionalDataPoint[float]:
        """Implement PriceServiceInterface

        This implementation gets the price from the PulseX hosted subgraphs

        """

        asset = asset.lower()
        currency = currency.lower()

        if currency != "usd":
            logger.error(f"Currency not supported: {currency}")
            return None, None

        token = pulsex_subgraph_supporten_tokens.get(asset, None)
        if not token:
            logger.error(f"Asset not supported: {asset}")
            return None, None

        headers = {
            "Content-Type": "application/json",
        }

        query = "{ token(id: \"" + token.lower() + "\") { derivedUSD } }"

        json_data = {
            "query": query,
            "variables": None,
            "operationName": None,
        }

        request_url = self.url + "/subgraphs/name/pulsechain/pulsex"

        with requests.Session() as s:
            try:
                r = s.post(request_url, headers=headers, json=json_data, timeout=self.timeout)
                res = r.json()
                data = {"response": res}

            except requests.exceptions.ConnectTimeout:
                logger.warning("Timeout Error, No prices retrieved from PulseX Supgraph")
                return None, None

            except Exception as e:
                logger.warning(f"No prices retrieved from PulseX Supgraph with Exception {e}")
                return None, None

        if "error" in data:
            logger.error(data)
            return None, None

        elif "response" in data:
            response = data["response"]

            try:
                if response["data"]["token"] == None:
                    logger.error(f"No data found for the token {token}")
                    logger.info(f"It is possible that no Liquidity Pool exists including this token ({token})")
                    return None, None

                price = float(response["data"]["token"]["derivedUSD"])
                return price, datetime_now_utc()
            except KeyError as e:
                msg = f"Error parsing Pulsechain Supgraph response: KeyError: {e}"
                if ("data" in response and
                    "token" in response["data"] and
                    response["data"]["token"] == None):
                    msg = f"Invalid token address: {token}"
                logger.critical(msg)
                return None, None

        else:
            logger.error("Invalid response from get_url")
            return None, None


@dataclass
class PulseXSupgraphSource(PriceSource):
    asset: str = ""
    currency: str = ""
    service: PulseXSupgraphService = field(default_factory=PulseXSupgraphService, init=False)
