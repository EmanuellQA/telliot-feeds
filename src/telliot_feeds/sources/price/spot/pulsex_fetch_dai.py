from dataclasses import dataclass
from dataclasses import field
from typing import Any

from dotenv import load_dotenv

from telliot_feeds.dtypes.datapoint import OptionalDataPoint
from telliot_feeds.pricing.price_service import WebPriceService
from telliot_feeds.pricing.price_source import PriceSource
from telliot_feeds.utils.log import get_logger

from web3 import Web3
import os

load_dotenv()
logger = get_logger(__name__)

def get_amount_out(amount_in, reserve_in, reserve_out):
    """
    Given an input asset amount, returns the maximum output amount of the
    other asset (accounting for fees) given reserves.

    :param amount_in: Amount of input asset.
    :param reserve_in: Reserve of input asset in the pair contract.
    :param reserve_out: Reserve of input asset in the pair contract.
    :return: Maximum amount of output asset.
    """
    assert amount_in > 0
    assert reserve_in > 0 and reserve_out > 0
    amount_in_with_fee = amount_in * 997
    numerator = amount_in_with_fee * reserve_out
    denominator = reserve_in * 1000 + amount_in_with_fee
    return int(numerator / denominator)


class PulseXFETCHDAIService(WebPriceService):
    """Pulsechain PulseX Price Service for FETCH/USD feed"""

    def __init__(self, **kwargs: Any) -> None:
        kwargs["name"] = "Fetch Price Service"
        kwargs["url"] = os.getenv("LP_PULSE_NETWORK_URL", "https://rpc.v4.testnet.pulsechain.com")
        kwargs["timeout"] = 10.0
        super().__init__(**kwargs)

    async def get_price(self, asset: str, currency: str) -> OptionalDataPoint[float]:
        asset = asset.lower()
        currency = currency.lower()

        if asset != "fetch":
            logger.error(f"Asset not supported: {asset}")
            return None, None

        if currency not in ["dai", "pls", "usdt", "usdc"]:
            logger.error(f"Currency not supported: {currency}")
            return None, None

        GET_RESERVERS_ABI = '[{"inputs":[],"name":"getReserves","outputs":[{"internalType":"uint112","name":"reserve0","type":"uint112"},{"internalType":"uint112","name":"reserve1","type":"uint112"},{"internalType":"uint32","name":"blockTimestampLast","type":"uint32"}],"stateMutability":"view","type":"function"}]'

        w3 = Web3(Web3.HTTPProvider(self.url, request_kwargs={"timeout": self.timeout}))

        lp_wpls_fetch = w3.toChecksumAddress(os.getenv("LP_WPLS_FETCH", "0x36b7D3C9Dd22050d06A9D262640Ae3D626e77439"))
        try:
            contract = w3.eth.contract(address=lp_wpls_fetch, abi=GET_RESERVERS_ABI)
            [reserve0, reserve1, timestamp] = contract.functions.getReserves().call()
            token0, _ = [token.strip() for token in os.getenv("LP_FETCH_PAIR", "wpls/fetch").split('/')]
            if "fetch" not in token0:
                reserve0, reserve1 = reserve1, reserve0

            val = get_amount_out(1e18, reserve0, reserve1)

            vl0 = ((1e18 * reserve1) / (reserve0 + 1e18)) * reserve0  # value locked token0 without fees
            vl1 = ((1e18 * reserve0) / (reserve1 + 1e18)) * reserve1  # value locked token0 without fees
            tvl = vl0 + vl1  # total value locked of the pool
        except Exception as e:
            logger.warning(
                f"No prices retrieved from Pulsechain Sec Oracle with Exception {e}"
            )
            return None, None

        lp_wpls_tdai = w3.toChecksumAddress(os.getenv("LP_WPLS_TDAI", "0xA2D510bf42D2B9766DB186F44a902228E76ef262"))
        pls_price = None
        try:        
            if currency == "pls":
                contract = w3.eth.contract(address=lp_wpls_tdai, abi=GET_RESERVERS_ABI)
                [reserve0, reserve1, timestamp] = contract.functions.getReserves().call()
                token0, _ = [token.strip() for token in os.getenv("LP_DAI_PAIR", "wpls/dai").split('/')]
                if "wpls" not in token0:
                    reserve0, reserve1 = reserve1, reserve0
                pls_price = get_amount_out(1e18, reserve0, reserve1)
        except Exception as e:
            logger.warning(
                f"No prices retrieved from Pulsechain Sec Oracle with Exception {e}"
            )
            return None, None

        try:
            price = float(val / 1e18)
            if currency == "pls" and pls_price is not None:
                price = float(price * pls_price / 1e18)
            if currency == "usdc" or currency == "usdt":
                price = price * 1e12
            return price, timestamp, float(tvl)
        except Exception as e:
            msg = f"Error parsing Pulsechain Sec Oracle response: KeyError: {e}"
            logger.critical(msg)
            return None, None


@dataclass
class PulseXFETCHDAISource(PriceSource):
    asset: str = ""
    currency: str = ""
    addr: str = ""
    service: PulseXFETCHDAIService = field(default_factory=PulseXFETCHDAIService, init=False)
