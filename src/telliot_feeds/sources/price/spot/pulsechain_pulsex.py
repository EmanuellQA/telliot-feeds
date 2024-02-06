from dataclasses import dataclass
from dataclasses import field
from typing import Any

from dotenv import load_dotenv

from telliot_feeds.dtypes.datapoint import datetime_now_utc
from telliot_feeds.dtypes.datapoint import OptionalDataPoint
from telliot_feeds.pricing.price_service import WebPriceService
from telliot_feeds.pricing.price_source import PriceSource
from telliot_feeds.utils.log import get_logger

from web3 import Web3
import os
import requests
import math
from decimal import Decimal

DEXSCREENER_BASE_URL = "https://api.dexscreener.com/latest/dex/pairs/pulsechain"

URLS = {
    'usdt': 'https://api.dexscreener.com/latest/dex/pairs/pulsechain/0x322Df7921F28F1146Cdf62aFdaC0D6bC0Ab80711',
    'usdc': 'https://api.dexscreener.com/latest/dex/pairs/pulsechain/0x6753560538ECa67617A9Ce605178F788bE7E524E',
    'dai': 'https://api.dexscreener.com/latest/dex/pairs/pulsechain/0xe56043671df55de5cdf8459710433c10324de0ae'
    
}

class bcolors:
    green = '\033[92m'
    red = '\033[91m'
    yellow = '\033[93m'
    endc = '\033[0m'


load_dotenv()

DEFAULT_LP_CURRENCIES = ['usdt', 'usdc', 'dai']
DEFAULT_LP_ADDRESSES = [
    '0x322Df7921F28F1146Cdf62aFdaC0D6bC0Ab80711',
    '0x6753560538ECa67617A9Ce605178F788bE7E524E',
    '0xE56043671df55dE5CDf8459710433C10324DE0aE'
]
DEFAULT_LP_CURRENCY_ORDER = [
    'usdt/wpls',
    'usdc/wpls',
    'wpls/dai'
]

def get_lps_contract_addressses():
    currency_sources = os.getenv("PLS_CURRENCY_SOURCES")
    address_sources = os.getenv("PLS_ADDR_SOURCES")
    if not currency_sources or not address_sources:
        return {currency: address for currency, address in zip(DEFAULT_LP_CURRENCIES, DEFAULT_LP_ADDRESSES)}
    addrs = {}
    sources_list = currency_sources.split(',')
    sources_addr_list = address_sources.split(',')
    for i,s in enumerate(sources_list):
        addrs[s] = Web3.toChecksumAddress(sources_addr_list[i])
    return addrs

addrs = get_lps_contract_addressses()        

def get_lps_currency_order():
    currency_sources = os.getenv("PLS_CURRENCY_SOURCES")
    currency_order = os.getenv("PLS_LPS_ORDER")
    if not currency_sources or not currency_order:
        return {currency: order for currency, order in zip(DEFAULT_LP_CURRENCIES, DEFAULT_LP_CURRENCY_ORDER)}
    pls_lps_order = {}
    sources_list = currency_sources.split(',')
    sources_lps_list = currency_order.split(',')
    for i,s in enumerate(sources_list):
        pls_lps_order[s] = sources_lps_list[i].lower()
    return pls_lps_order

pls_lps_order = get_lps_currency_order()

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
    amount_in_with_fee = amount_in*1000
    numerator = amount_in_with_fee*reserve_out
    denominator = reserve_in*1000 + amount_in_with_fee
    return float(numerator/denominator)

class PulsechainPulseXService(WebPriceService):
    """Pulsechain PulseX Price Service for PLS/USD feed"""

    def __init__(self, **kwargs: Any) -> None:
        kwargs["name"] = "LiquidLoans PulseX Price Service"
        kwargs["url"] = os.getenv("LP_PULSE_NETWORK_URL", "https://rpc.pulsechain.com")
        kwargs["timeout"] = 10.0
        self.debugging_price = os.getenv("DEBUGGING_PRICE", 'False').lower() in ('true', '1', 't')
        self.absolute_tolerance = float(os.getenv("PRICE_DIFF_ABSOLUTE_TOLERANCE", 1e-2))
        super().__init__(**kwargs)

    async def get_price(self, asset: str, currency: str) -> OptionalDataPoint[float]:
        """Implement PriceServiceInterface

        This implementation gets the price from the Pulsechain PulseX Service

        """

        asset = asset.lower()
        currency = currency.lower()

        if currency not in  ["usdc", "dai", "usdt"]:
            logger.error(f"Currency not supported: {currency}")
            return None, None

        contract_addr = addrs.get(currency)
        
        if asset != 'pls' and asset != 'validated-feed':
            logger.error(f"Asset not supported: {asset}")
            return None, None

        getReservesAbi = '[{"inputs":[],"name":"getReserves","outputs":[{"internalType":"uint112","name":"reserve0","type":"uint112"},{"internalType":"uint112","name":"reserve1","type":"uint112"},{"internalType":"uint32","name":"blockTimestampLast","type":"uint32"}],"stateMutability":"view","type":"function"}]'
        w3 = Web3(Web3.HTTPProvider(self.url, request_kwargs={'timeout': self.timeout}))
        try:
            contract = w3.eth.contract(address=contract_addr, abi=getReservesAbi)
            [reserve0, reserve1, timestamp] = contract.functions.getReserves().call()
            token0, _ = pls_lps_order[currency].split('/')
            if "pls" not in token0.strip():
                reserve0, reserve1 = reserve1, reserve0

            logger.info(f"""
                Debugging reservers for {asset}-{currency}:
                reserve0: {reserve0}
                reserve1: {reserve1}
            """)

            val = get_amount_out(1e18, reserve0, reserve1)

            if currency == 'usdc' or currency == 'usdt':
                reserve1 = reserve1 * 1e12

            vl0 = ((1e18 * reserve1) / (reserve0 + 1e18)) * reserve0 #value locked token0 without fees
            vl1 = ((1e18 * reserve0) / (reserve1 + 1e18)) * reserve1 #value locked token0 without fees
            tvl = vl0 + vl1 #total value locked of the pool

        except Exception as e:
            logger.warning(f"No prices retrieved from Pulsechain Sec Oracle with Exception {e}")
            return None, None

        try:
            price = w3.fromWei(val, 'ether')
            if currency == 'usdc' or currency == 'usdt':
                price = price * Decimal(1e12) #scale usdc 

            logger.info(f"""
                LP price for {asset}-{currency}: {price}
                LP contract address: {contract_addr}
            """) 
            
            if asset == "validated-feed":
                try:
                    r = requests.get(f'{DEXSCREENER_BASE_URL}/{contract_addr}')
                    
                    priceUsd = Decimal(r.json()['pair']['priceUsd'])
                    logger.info(f"""
                        Dexscreener API priceUsd: {priceUsd}
                        LP address ({asset}-{currency}): {contract_addr}
                        LP price: {price}
                        Abs Diff: {abs(priceUsd - price)}
                        Abs tolereance: {self.absolute_tolerance}
                        Is close? {math.isclose(priceUsd, price, abs_tol=self.absolute_tolerance)}
                    """)
                    if not math.isclose(priceUsd, price, abs_tol=self.absolute_tolerance):
                        logger.warning(f"Price from dexscreener API is different from LP price")
                        return None, None
                except Exception as e:
                    logger.error(f"Error fetching dexscreener API: {e}")
                    return None, None

            if self.debugging_price:
                r = requests.get(URLS[currency])

                pair = r.json()['pair']
                priceUsd = Decimal(pair['priceUsd'])

                logger.debug(f'{bcolors.yellow}')
                logger.debug(pair)
                logger.debug(f'{bcolors.endc}')

                priceUsd_copy = priceUsd * Decimal(1e5)
                price_copy = price * Decimal(1e5)
                if math.isclose(priceUsd_copy, price_copy, abs_tol=1e-2):
                    logger.debug(f"{bcolors.green}")
                    logger.debug(f"""
                        For better visualization the prices are multiplied by 1e5
                        priceUsd * 1e5: {priceUsd_copy}
                        price * 1e5: {price_copy}

                        Price CORRECT ({asset}-{currency}):
                        Pair dexscreener API priceUsd: {priceUsd_copy}
                        Reported price rounded: {round(price_copy, 8)}
                        math.isclose(priceUsd, price, abs_tol=1e-2): {math.isclose(priceUsd_copy, price_copy, abs_tol=1e-2)}

                        Abs Diff:
                        abs(priceUsd - price): {abs(priceUsd_copy - price_copy)}

                        Percentual Diffs (for 1.5%):
                        abs((priceUsd - price) / price): {abs((priceUsd_copy - price_copy) / price_copy)}
                        abs((priceUsd - price) / ((priceUsd + price) / 2)): {abs((priceUsd - price) / ((priceUsd + price) / 2))}
                        abs((priceUsd - price) / price) <= 0.015 : {abs((priceUsd_copy - price_copy) / price_copy) <= 0.015}
                        abs((priceUsd - price) / ((priceUsd + price) / 2)) <= 0.015: {abs((priceUsd - price) / ((priceUsd + price) / 2)) <= 0.015}
                    """)
                    logger.debug(f'{bcolors.endc}')
                else:
                    logger.debug(f"{bcolors.red}")
                    logger.debug(f"""
                        For better visualization the prices are multiplied by 1e5
                        priceUsd * 1e5: {priceUsd_copy}
                        price * 1e5: {price_copy}

                        Price INCORRECT ({asset}-{currency}):
                        Pair dexscreener API priceUsd: {priceUsd_copy}
                        Reported price rounded: {round(price_copy, 8)}
                        math.isclose(priceUsd, price, abs_tol=1e-2): {math.isclose(priceUsd_copy, price_copy, abs_tol=1e-2)}

                        Abs Diff:
                        abs(priceUsd - price): {abs(priceUsd_copy - price_copy)}

                        Percentual Diffs (for 1.5%):
                        abs((priceUsd - price) / price): {abs((priceUsd_copy - price_copy) / price_copy)}
                        abs((priceUsd - price) / ((priceUsd + price) / 2)): {abs((priceUsd - price) / ((priceUsd + price) / 2))}
                        abs((priceUsd - price) / price) <= 0.015 : {abs((priceUsd_copy - price_copy) / price_copy) <= 0.015}
                        abs((priceUsd - price) / ((priceUsd + price) / 2)) <= 0.015: {abs((priceUsd - price) / ((priceUsd + price) / 2)) <= 0.015}
                    """)
                    logger.debug(f'{bcolors.endc}')
            
            return float(price), timestamp, float(tvl)
        except Exception as e:
            msg = f"Error parsing Pulsechain Sec Oracle response: KeyError: {e}"
            logger.critical(msg)
            return None, None

@dataclass
class PulsechainPulseXSource(PriceSource):
    asset: str = ""
    currency: str = ""
    addr: str = ""
    service: PulsechainPulseXService = field(default_factory=PulsechainPulseXService, init=False)
