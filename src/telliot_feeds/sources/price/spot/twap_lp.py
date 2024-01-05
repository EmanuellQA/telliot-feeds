import os
from decimal import *
from pathlib import Path
import asyncio

from dataclasses import dataclass
from dataclasses import field
from typing import Any
from web3 import Web3

import json

from telliot_feeds.dtypes.datapoint import datetime_now_utc
from telliot_feeds.dtypes.datapoint import OptionalDataPoint
from telliot_feeds.pricing.price_service import WebPriceService
from telliot_feeds.pricing.price_source import PriceSource
from telliot_feeds.utils.log import get_logger


logger = get_logger(__name__)

class TWAPLPSpotPriceService(WebPriceService):
    """TWAP Price Service"""
    ABI = """
    [
        {
            "inputs": [],
            "name": "getReserves",
            "outputs": [
            { "internalType": "uint112", "name": "reserve0", "type": "uint112" },
            { "internalType": "uint112", "name": "reserve1", "type": "uint112" },
            {
                "internalType": "uint32",
                "name": "blockTimestampLast",
                "type": "uint32"
            }
            ],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "type": "function",
            "stateMutability": "view",
            "payable": false,
            "outputs": [{ "type": "uint256", "name": "", "internalType": "uint256" }],
            "name": "price0CumulativeLast",
            "inputs": [],
            "constant": true
        },
        {
            "type": "function",
            "stateMutability": "view",
            "payable": false,
            "outputs": [{ "type": "uint256", "name": "", "internalType": "uint256" }],
            "name": "price1CumulativeLast",
            "inputs": [],
            "constant": true
        }
    ]
    """
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

    def __init__(self, **kwargs: Any) -> None:
        kwargs["name"] = "TWAP LP Price Service"
        kwargs["url"] = os.getenv("LP_PULSE_NETWORK_URL", "https://rpc.pulsechain.com")
        kwargs["timeout"] = 10.0

        self.prevPricesPath: Path = Path('./prevPricesCumulative.json') 
        self.max_retries = int(os.getenv('MAX_RETRIES', 5))
        self.TWAP_TIMESPAN = int(os.getenv('TWAP_TIMESPAN', 1800))
        self.FETCH_LP_INTERVAL = int(os.getenv('FETCH_LP_INTERVAL', 60))

        self.isSourceInitialized = False

        self.isTwapServiceActive = False

        self.DATA_POINTS_LIMIT = int(os.getenv('DATA_POINTS_LIMIT', 10000))

        super().__init__(**kwargs)

    async def handleInitializeSource(self, currency: str):
        if self.isSourceInitialized: return
        self.isSourceInitialized = True
        self.contract_addresses: dict[str, str] = self._get_contract_address()
        self.lps_order: dict[str, str] = self._get_lps_order()
        self.reporter_event_loop = asyncio.get_running_loop()
        logger.info(f"Reporter: initial startup waiting TWAP period ({self.TWAP_TIMESPAN} seconds)")
        price0CumulativeLast, price1CumulativeLast, reserve0, reserve1, blockTimestampLast = self._callPricesCumulativeLast(
            self.contract_addresses[currency]
        )
        key = self._get_pair_json_key(currency)
        self._update_cumulative_prices_json(
            price0CumulativeLast,
            price1CumulativeLast,
            reserve0,
            reserve1,
            blockTimestampLast,
            key
        )
        await self.handleActivateTwapService(currency)
        await asyncio.sleep(self.TWAP_TIMESPAN)
        logger.info(f"REPORTER: JSON {key} initialized")

    async def handleActivateTwapService(self, currency: str):
        if self.isTwapServiceActive: return
        self.isTwapServiceActive = True
        asyncio.create_task(self.initializeTwapService(currency))
        await asyncio.sleep(0)

    async def _update_cumulative_prices_json_after_time(self, wait_time: int, contract_address: str, key: str):
        logger.info(f"TWAP Service: waiting {wait_time:.2f} seconds to update cumulative prices data")
        await asyncio.sleep(wait_time)
        price0CumulativeLast, price1CumulativeLast, reserve0, reserve1, blockTimestampLast = self._callPricesCumulativeLast(
            contract_address
        )
        self._update_cumulative_prices_json(
            price0CumulativeLast,
            price1CumulativeLast,
            reserve0,
            reserve1,
            blockTimestampLast,
            key
        )
        logger.info(f"TWAP Service: updated cumulative prices {key} data in {self.prevPricesPath.resolve()}")

    async def initializeTwapService(self, currency: str):
        logger.info(
            f"""
            TWAP Service: initializing TWAP service for {currency}
            TWAP fetch interval: {self.FETCH_LP_INTERVAL} seconds
            """
        )

        key = self._get_pair_json_key(currency)
        contract_address = self.contract_addresses[currency]

        while True:
            await self._update_cumulative_prices_json_after_time(self.FETCH_LP_INTERVAL, contract_address, key)
            await asyncio.sleep(0)

    def _get_contract_address(self) -> dict[str, str]:
        address_sources = os.getenv("PLS_ADDR_SOURCES")
        currency_sources = os.getenv("PLS_CURRENCY_SOURCES")

        if not address_sources or not currency_sources:
            return {currency: address for currency, address in zip(self.DEFAULT_LP_CURRENCIES, self.DEFAULT_LP_ADDRESSES)}

        addrs = {}
        sources_list = currency_sources.split(',')
        sources_addr_list = address_sources.split(',')

        if len(sources_list) != len(sources_addr_list):
            raise Exception('PLS_CURRENCY_SOURCES and PLS_ADDR_SOURCES must have the same length')

        for i,s in enumerate(sources_list):
            addrs[s] = Web3.toChecksumAddress(sources_addr_list[i])
        return addrs

    def _get_lps_order(self) -> dict[str, str]:
        currency_sources = os.getenv("PLS_CURRENCY_SOURCES")
        currency_order = os.getenv("PLS_LPS_ORDER")
        if not currency_sources or not currency_order:
            return {currency: order for currency, order in zip(self.DEFAULT_LP_CURRENCIES, self.DEFAULT_LP_CURRENCY_ORDER)}

        lps_order = {}
        sources_list = currency_sources.split(',')
        order_list = currency_order.split(',')
        if len(sources_list) != len(order_list):
            raise Exception('PLS_CURRENCY_SOURCES and PLS_ADDR_SOURCES must have the same length')
        for i,s in enumerate(sources_list):
            lps_order[s] = order_list[i].lower()
        return lps_order
    
    def _callGetReserves(self, contract_address: str):
        retry_count = 0
        while retry_count < self.max_retries:
            try:
                w3 = Web3(Web3.HTTPProvider(self.url, request_kwargs={'timeout': self.timeout}))
                contract = w3.eth.contract(address=contract_address, abi=self.ABI)
                reserve0, reserve1, blockTimestamp = contract.functions.getReserves().call()
                logger.debug(f"""
                _callGetReserves({contract_address}) returned:
                                reserve0: {reserve0}
                                reserve1: {reserve1}
                                blockTimestamp: {blockTimestamp}
                            """)
                return reserve0, reserve1, blockTimestamp
            except Exception as e:
                retry_count += 1
                logger.error(
                    f"""
                    Error calling RPC 'getReserves'
                    {'' if retry_count == self.max_retries else 'Trying again...'}
                    """
                )
        raise Exception(f"Failed to call RPC 'getReserves', address {contract_address}")

    def _callPricesCumulativeLast(self, contract_address: str) -> tuple[int]:
        retry_count = 0
        while retry_count < self.max_retries:
            try:
                w3 = Web3(Web3.HTTPProvider(self.url, request_kwargs={'timeout': self.timeout}))
                contract = w3.eth.contract(address=contract_address, abi=self.ABI)
                price0CumulativeLast = contract.functions.price0CumulativeLast().call()
                price1CumulativeLast = contract.functions.price1CumulativeLast().call()
                reserve0, reserve1, _blockTimestampLast = contract.functions.getReserves().call()
                #reserve0, reserve1, _blockTimestampLast = self._callGetReserves(contract_address)
                logger.debug(f"""   
                _callPricesCumulativeLast({contract_address}) returned:
                                price0CumulativeLast: {price0CumulativeLast}
                                price1CumulativeLast: {price1CumulativeLast}
                                reserve0: {reserve0}
                                reserve1: {reserve1}
                                _blockTimestampLast: {_blockTimestampLast}
                          """)
                return price0CumulativeLast, price1CumulativeLast, reserve0, reserve1, _blockTimestampLast
            except Exception as e:
                retry_count += 1
                logger.error(
                    f"""
                    Error calling RPC in '_callPricesCumulativeLast' method
                    {'' if retry_count == self.max_retries else 'Trying again...'}
                    """
                )
                logger.error(e)
        raise Exception(f"Failed to call RPC in '_callPricesCumulativeLast' method, address {contract_address}")
    
    def _get_pair_json_key(self, currency: str) -> str:
        token0, token1 = self.lps_order[currency].split('/')
        return f"{token0.upper()}/{token1.upper()}"
    
    def _read_cumulative_prices_json(self) -> dict:
        if self.prevPricesPath.exists():
            if os.stat(self.prevPricesPath.resolve()).st_size == 0:
                logger.info(f'Empty Cumulative prices JSON file found ({self.prevPricesPath.resolve()}), initializing...')
                return {}
            return json.loads(self.prevPricesPath.read_text())
        return {}

    def _update_cumulative_prices_json(
        self,
        price0CumulativeLast: int,
        price1CumulativeLast: int,
        reserve0: int,
        reserve1: int,
        blockTimestampLast: int,
        key: str
    ) -> None:
        json_data = self._read_cumulative_prices_json()

        if key not in json_data.keys():
            json_data[key] = []

        if type(json_data[key]) != list:
            logger.info(f"Found old invalid JSON format, initializing {key} to a list of data points")
            json_data[key] = []

        if len(json_data[key]) > 0:
            last_data_point = json_data[key][-1]
            if (
                last_data_point['price0CumulativeLast'] == str(price0CumulativeLast) or
                last_data_point['price1CumulativeLast'] == str(price1CumulativeLast) or
                last_data_point['reserve0'] == str(reserve0) or
                last_data_point['reserve1'] == str(reserve1) or
                last_data_point['blockTimestampLast'] == str(blockTimestampLast)
            ):
                logger.info(f"Last data point in {key} JSON is the same as the current one, skipping update")
                return

        new_data = {
            'price0CumulativeLast': str(price0CumulativeLast),
            'price1CumulativeLast': str(price1CumulativeLast),
            'reserve0': str(reserve0),
            'reserve1': str(reserve1),
            'blockTimestampLast': str(blockTimestampLast)
        }
        logger.debug(f"""
            *****Appending {key} JSON data point*****:
            key: {key}
            price0CumulativeLast: {price0CumulativeLast}
            price1CumulativeLast: {price1CumulativeLast}
            reserve0: {reserve0}
            reserve1: {reserve1}
            blockTimestampLast: {blockTimestampLast}
        """)

        json_data[key].append(new_data)

        if len(json_data[key]) > self.DATA_POINTS_LIMIT:
            logger.info(f'JSON {key} data points limit reached ({self.DATA_POINTS_LIMIT}), removing oldest data point')
            threshold = len(json_data[key]) - self.DATA_POINTS_LIMIT
            json_data[key] = json_data[key][threshold:]

        self.prevPricesPath.write_text(json.dumps(json_data))
        logger.info(f'Entry {key} updated in Cumulative prices JSON')

    def get_prev_prices_cumulative(self, currency: str, currentBlockTimestampLast) -> tuple[int]:
        key = self._get_pair_json_key(currency)

        json_data = self._read_cumulative_prices_json()

        if key not in json_data.keys():
            address = self.contract_addresses[currency]
            price0CumulativeLast, price1CumulativeLast, reserve0, reserve1, _blockTimestampLast = self._callPricesCumulativeLast(address)
            self._update_cumulative_prices_json(
                price0CumulativeLast,
                price1CumulativeLast,
                reserve0,
                reserve1,
                _blockTimestampLast,
                key
            )
            logger.info(f'Cumulative prices JSON {key} data initialized in get_prev_prices_cumulative')
            logger.debug(f"""   
                        call get_prev_prices_cumulative({currency}) returned:
                                price0CumulativeLast: {price0CumulativeLast}
                                price1CumulativeLast: {price1CumulativeLast}
                                reserve0: {reserve0}
                                reserve1: {reserve1}
                                _blockTimestampLast: {_blockTimestampLast}
                          """)
            return price0CumulativeLast, price1CumulativeLast, _blockTimestampLast

        logger.info(f'Cumulative prices JSON {key} data found, list with {len(json_data[key])} data points)')
        try:
            data_points = json_data[key]
            
            twap_data_point = None
            _blockTimestampLast = None
            for data_point in reversed(data_points):
                _blockTimestampLast = int(data_point['blockTimestampLast'])
                time_diff = currentBlockTimestampLast - _blockTimestampLast
                if time_diff >= self.TWAP_TIMESPAN:
                    twap_data_point = data_point
                    break
            
            if twap_data_point is None:
                twap_data_point = data_points[0]
                logger.error(f"""
                    No TWAP data point found where in Cumulative prices JSON file where:
                    time_diff = {currentBlockTimestampLast} - {_blockTimestampLast}
                    using oldest data point:
                    prevPrice0CumulativeLast = {twap_data_point['price0CumulativeLast']}
                    prevPrice1CumulativeLast = {twap_data_point['price1CumulativeLast']}
                    reserve0 = {twap_data_point['reserve0']}
                    reserve1 = {twap_data_point['reserve1']}
                    prevBlockTimestampLast = {twap_data_point['blockTimestampLast']}

                    currentBlockTimestampLast = {currentBlockTimestampLast}

                    Time difference: {currentBlockTimestampLast - int(twap_data_point['blockTimestampLast'])}
                """)
                
            logger.debug(f"""
                TWAP data point:
                prevPrice0CumulativeLast = {twap_data_point['price0CumulativeLast']}
                prevPrice1CumulativeLast = {twap_data_point['price1CumulativeLast']}
                reserve0 = {twap_data_point['reserve0']}
                reserve1 = {twap_data_point['reserve1']}
                prevBlockTimestampLast = {twap_data_point['blockTimestampLast']}
            """)
            
            prevPrice0CumulativeLast = int(twap_data_point['price0CumulativeLast'])
            prevPrice1CumulativeLast = int(twap_data_point['price1CumulativeLast'])
            reserve0 = int(twap_data_point['reserve0'])
            reserve1 = int(twap_data_point['reserve1'])
            prevBlockTimestampLast = int(twap_data_point['blockTimestampLast'])

            time_elapsed = currentBlockTimestampLast - prevBlockTimestampLast
            logger.debug(f"time elapsed since last TWAP data point: {time_elapsed}")
            if time_elapsed > self.TWAP_TIMESPAN:
                time_diff = time_elapsed - self.TWAP_TIMESPAN
                expected_prevBlockTimestampLast = prevBlockTimestampLast + time_diff
                logger.debug(f"""
                    time_diff = {time_diff} ({time_elapsed} - {self.TWAP_TIMESPAN})
                    expected_prevBlockTimestampLast = {expected_prevBlockTimestampLast} ({prevBlockTimestampLast} + {time_diff})
                    Time elapsed since last TWAP data point is greater than {self.TWAP_TIMESPAN} seconds,
                    updating previous data point ({prevBlockTimestampLast}) to {expected_prevBlockTimestampLast})
                """)
                prevPrice0CumulativeLast, prevPrice1CumulativeLast = self._calculate_cumulative_price(
                    self.contract_addresses[currency],
                    prevPrice0CumulativeLast,
                    prevPrice1CumulativeLast,
                    prevBlockTimestampLast,
                    expected_prevBlockTimestampLast,
                    reserve0,
                    reserve1
                )
                prevBlockTimestampLast = expected_prevBlockTimestampLast

            logger.debug(f"""   
                        call get_prev_prices_cumulative({currency}) returned:
                                prevPrice0CumulativeLast: {prevPrice0CumulativeLast}
                                prevPrice1CumulativeLast: {prevPrice1CumulativeLast}
                                reserve0: {reserve0}
                                reserve1: {reserve1}
                                prevBlockTimestampLast:  {prevBlockTimestampLast}
                          """)
            return prevPrice0CumulativeLast, prevPrice1CumulativeLast, prevBlockTimestampLast
        except (json.decoder.JSONDecodeError, ValueError) as e: 
            logger.error(f"""
            Error while reading Cumulative Prices JSON file:
            {self.prevPricesPath.resolve()}
            You can manually delete the file and restart the service to automatically initialize it

            The expected JSON format is:
            {{
                "WPLS/DAI": [{{
                    "price0CumulativeLast": "123456789",
                    "price1CumulativeLast": "123456789",
                    "blockTimestampLast": "123456789"
                }}],
                ...
            }}
            """)
            logger.error(e)

    def _get_current_block_timestamp(self):
        logger.debug(f"""   
                        call _get_current_block_timestamp():
                     """)
        w3 = Web3(Web3.HTTPProvider(self.url))
        block = w3.eth.getBlock("latest")
        timestamp = block.timestamp
        timestamp = timestamp % 2**32
        logger.debug(f"""   
                        returned timestamp {timestamp}
                     """)
        return timestamp
    
    def _calculate_cumulative_price(
        self, address: str,
        price0Cumulative: int,
        price1Cumulative: int,
        blockTimestampLast: int,
        currentTimesamp: int,
        reserve0,
        reserve1
    ) -> tuple[int]:
        logger.debug(f"""   
                        call _calculate_cumulative_price({address}, 
                                                         {price0Cumulative}, 
                                                         {price1Cumulative}, 
                                                         {blockTimestampLast}, 
                                                         {currentTimesamp}),
                                                         {reserve0},
                                                         {reserve1}):
                          """)

        timeElapsed = currentTimesamp - blockTimestampLast
        logger.debug(f"""   
                    timeElapsed: {timeElapsed}
                    """)
        logger.debug(f"""   
                    reserve0: {reserve0}
                    reserve1: {reserve1}
                    """)
        fixed_point_fraction0 = (reserve1 / reserve0) * (2 ** 112)
        fixed_point_fraction1 = (reserve0 / reserve1) * (2 ** 112)
        logger.debug(f"""   
                    fixed_point_fraction0: {fixed_point_fraction0}
                    fixed_point_fraction1: {fixed_point_fraction1}
                    """)
        price0Cumulative += int(fixed_point_fraction0) * timeElapsed
        price1Cumulative += int(fixed_point_fraction1) * timeElapsed
        logger.debug(f"""   
                    returned:
                    price0Cumulative: {price0Cumulative}, 
                    price1Cumulative: {price1Cumulative}:
                    """)

        return price0Cumulative, price1Cumulative

    def get_currentPrices(
        self,
        currency: str
    ) -> tuple[int]:
        address = self.contract_addresses[currency]

        price0CumulativeLast, price1CumulativeLast, reserve0, reserve1, blockTimestampLast = self._callPricesCumulativeLast(address)

        logger.debug(f"""
            get_currentPrices({currency}) called, values returned:
            price0CumulativeLast: {price0CumulativeLast}
            price1CumulativeLast: {price1CumulativeLast}
            reserve0: {reserve0}
            reserve1: {reserve1}
            blockTimestampLast: {blockTimestampLast}
        """)

        blockTimestamp = self._get_current_block_timestamp()
        logger.debug(f"Blockchain blockTimestamp: {blockTimestamp}")
        if blockTimestamp != blockTimestampLast:
            logger.info(
                f"""
                blockTimestamp != blockTimestampLast:
                blockTimestamp / blockTimestampLast: {blockTimestamp} / {blockTimestampLast}
                Updating cumulative prices according to current block timestamp, current values:
                price0CumulativeLast: {price0CumulativeLast}
                price1CumulativeLast: {price1CumulativeLast}
                blockTimestampLast: {blockTimestampLast}
                """
            )
            price0CumulativeLast, price1CumulativeLast = self._calculate_cumulative_price(
                address,
                price0CumulativeLast,
                price1CumulativeLast,
                blockTimestampLast,
                blockTimestamp,
                reserve0,
                reserve1
            )
            logger.info(
                f"""
                Updated cumulative prices:
                currentBlockTimestamp: {blockTimestamp}
                currentPrice0: {price0CumulativeLast}
                currentPrice1: {price1CumulativeLast}
                """
            )
        return price0CumulativeLast, price1CumulativeLast, reserve0, reserve1, blockTimestamp
        
    def calculate_twap(
        self,
        currentPrice: int,
        prevPrice: int,
        blockTimestampLast: int,
        prevBlockTimestampLast: int,
    ) -> float:
        priceCumulativeDiff = (currentPrice - prevPrice) / 2**112
        timestampDiff = blockTimestampLast - prevBlockTimestampLast
        twap_price = priceCumulativeDiff / timestampDiff
        logger.info(
            f"""
            Calculated TWAP price:
            priceCumulativeDiff = ({currentPrice} - {prevPrice}) / 2**112
            timestampDiff = {blockTimestampLast} - {prevBlockTimestampLast}
            twap_price = priceCumulativeDiff / timestampDiff = {priceCumulativeDiff} / {timestampDiff}
            twap_price = {twap_price}
            """
        )
        return twap_price

    def _get_total_value_locked(self, currency: str, reserve0, reserve1):
        token0, _ = self.lps_order[currency].split('/')
        if "pls" not in token0.strip():
            reserve0, reserve1 = reserve1, reserve0

        if currency == 'usdc' or currency == 'usdt':
            reserve1 = reserve1 * 1e12

        vl0 = ((1e18 * reserve1) / (reserve0 + 1e18)) * reserve0 # value locked token0 without fees
        vl1 = ((1e18 * reserve0) / (reserve1 + 1e18)) * reserve1 # value locked token0 without fees
        tvl = vl0 + vl1 # total value locked of the pool
        return tvl

    async def get_price(self, asset: str, currency: str) -> OptionalDataPoint[float]:
        """Implement PriceServiceInterface"""

        asset = asset.lower()
        currency = currency.lower()

        if currency not in ["usdc", "dai", "usdt"]:
            logger.error(f"Currency not supported: {currency}")
            return None, None
        
        await self.handleInitializeSource(currency)

        try:
            price0CumulativeLast, price1CumulativeLast, reserve0, reserve1, blockTimestampLast = self.get_currentPrices(
                currency
            )

            prevPrice0CumulativeLast, prevPrice1CumulativeLast, prevBlockTimestampLast = self.get_prev_prices_cumulative(
                currency, blockTimestampLast
            )

            timeElapsed = blockTimestampLast - prevBlockTimestampLast
            if timeElapsed < self.TWAP_TIMESPAN:
                logger.info(
                    f"""
                    timeElapsed < self.TWAP_TIMESPAN = {timeElapsed} < {self.TWAP_TIMESPAN}:
                    Calculating TWAP price with current cumulative price for remaining time
                    """
                )
                remaining_time = self.TWAP_TIMESPAN - timeElapsed
                price0CumulativeLast, price1CumulativeLast = self._calculate_cumulative_price(
                    self.contract_addresses[currency],
                    price0CumulativeLast,
                    price1CumulativeLast,
                    blockTimestampLast,
                    blockTimestampLast + remaining_time,
                    reserve0,
                    reserve1
                )
                blockTimestampLast += remaining_time
                
            try:
                token0, _ = self.lps_order[currency].split('/')
                if "pls" in token0.strip():
                    logger.info("Using price0CumulativeLast")
                    twap = self.calculate_twap(
                        price0CumulativeLast,
                        prevPrice0CumulativeLast,
                        blockTimestampLast,
                        prevBlockTimestampLast,
                    )
                else:
                    logger.info("Using price1CumulativeLast")
                    twap = self.calculate_twap(
                        price1CumulativeLast,
                        prevPrice1CumulativeLast,
                        blockTimestampLast,
                        prevBlockTimestampLast,
                    )
            except KeyError as e:
                logger.error(f'currency {currency} not found in the provided PLS_CURRENCY_SOURCES')
                logger.error(e)

            price = float(twap)
            if currency == 'usdc' or currency == 'usdt':
                logger.info(
                    f"""
                    Scaling price for {currency} by 1e12:
                    {price} * 1e12 = {price * 1e12}
                    """
                )
                price = price * 1e12

            logger.info(f"""
            TWAP LP price for {asset}-{currency}: {price}
            LP contract address: {self.contract_addresses[currency]}
            """)

            weight = self._get_total_value_locked(currency, reserve0, reserve1)

            return price, datetime_now_utc(), float(weight)
        except Exception as e:
            logger.error(e)
            return None, None

@dataclass
class TWAPLPSpotPriceSource(PriceSource):
    asset: str = ""
    currency: str = ""
    service: TWAPLPSpotPriceService = field(default_factory=TWAPLPSpotPriceService, init=False)
