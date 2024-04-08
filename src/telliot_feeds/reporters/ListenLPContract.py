import os
from collections.abc import Callable
import logging
from logging.handlers import RotatingFileHandler
import time
import asyncio
import threading
from web3 import Web3
from web3.contract import Contract
from eth_abi import decode_abi
from telliot_feeds.utils.log import get_logger
from dotenv import load_dotenv

load_dotenv()

logger = get_logger(__name__)

class Contract:
    ABI = """
    [
    {
        "anonymous": false,
        "inputs": [
            {
                "indexed": false,
                "internalType": "uint112",
                "name": "reserve0",
                "type": "uint112"
            },
            {
                "indexed": false,
                "internalType": "uint112",
                "name": "reserve1",
                "type": "uint112"
            }
        ],
        "name": "Sync",
        "type": "event"
    }
    ]
    """
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

    def __init__(self, endpoint_url: str):
        logger.info(f"Initializing LP contract with endpoint_url={endpoint_url}")
        self.provider_url = endpoint_url
        self.w3 = Web3(Web3.HTTPProvider(self.provider_url))

    def _get_LPs_config(self):
        address_sources = os.getenv("PLS_ADDR_SOURCES")
        currency_order = os.getenv("PLS_LPS_ORDER")

        if not address_sources and not currency_order:
            return dict(zip(self.DEFAULT_LP_ADDRESSES, self.DEFAULT_LP_CURRENCY_ORDER))
        
        addresses = [Web3.toChecksumAddress(address.strip()) for address in address_sources.split(',')] 
        currencies = [currency.strip() for currency in currency_order.split(',')]
        assert len(addresses) == len(currencies), "Address sources and currency order must have the same length"
        return dict(zip(addresses, currencies))

    def _get_contract(self, address: str):
        logger.info(f"LP contract address = {address}")
        return self.w3.eth.contract(address=address, abi=self.ABI)

class ListenLPContract(Contract):
    def __init__(
            self,
            sync_event: threading.Event,
            time_limit_event: threading.Event,
            current_report_time: dict[str,int],
            fetch_new_datapoint: Callable
    ):
        super().__init__(os.getenv('LP_PULSE_NETWORK_URL', 'https://rpc.pulsechain.com'))
        self.lps_config: dict[str,str] = self._get_LPs_config()
        self.lps_contracts: list[Contract] = [self._get_contract(lp_address) for lp_address in self.lps_config.keys()]

        self.sync_event = sync_event
        self.time_limit_event = time_limit_event
        self.current_report_time = current_report_time
        self.time_limit = int(os.getenv('REPORT_TIME_LIMIT', 3600))
        self.percentage_change_threshold = float(os.getenv('PERCENTAGE_CHANGE_THRESHOLD', 0.005))
        self.fetch_new_datapoint = fetch_new_datapoint
        self.from_block = self.w3.eth.get_block_number()
        self.is_initialized = False

        self.reorg_safe_default = int(os.getenv('REORG_SAFE_DEFAULT', 10))

        logger.info(f"Time limit: {self.time_limit} seconds")
        logger.info(f"ListenLPContract percentage change threshold: {self.percentage_change_threshold} ({self.percentage_change_threshold * 100}%)")
    
    async def initialize_price(self):
        try:
            if self.is_initialized: return
            logger.info("Initializing value")
            value, _ = await self.fetch_new_datapoint()
            if value is None: raise Exception("Error fetching new datapoint for initialization")
            self.previous_value = value
            logger.info(f"Initialized with value: {value}")
            self.is_initialized = True
        except Exception as e:
            logger.error(f"Error initializing price: {e}")

    def _get_percentage_change(self, previous_value, value):
        percentage_change = ((value - previous_value) / previous_value) * 100
        return abs(percentage_change)

    async def _check_time_limit(self):
        time_elapsed = time.time() - self.current_report_time['timestamp']
        if time_elapsed > self.time_limit:
            if not self.time_limit_event.is_set():
                logger.info(f"Time limit reached, setting time limit event (time elapsed={time_elapsed:.2f}, time limit={self.time_limit})")
                value, _ = await self.fetch_new_datapoint()
                if value is None: raise Exception("Error fetching new datapoint for time limit event")
                self.previous_value = value
                self.time_limit_event.set()
                self.sync_event.set()

    def _address_to_pair_name(self, lp_address: str):
        return self.lps_config[lp_address]

    async def _handle_event(self, event):
        data_processed = event['data'][2:] if event['data'].startswith('0x') else event['data']
        reserve0, reserve1 = decode_abi(['uint112', 'uint112'], bytes.fromhex(data_processed))

        logger.info(f"""
            LP Sync event received:
            address: {event['address']}
            Pair: {self._address_to_pair_name(event['address'])}
            reserve0: {reserve0}
            reserve1: {reserve1}
        """)

        if self.is_sync_event_handled:
            logger.info(
                f"""
                Sync event already handled in the current poll:
                Pair: {self.pair_handled_data['name']}
                reserve0: {self.pair_handled_data['reserve0']}
                reserve1: {self.pair_handled_data['reserve1']}
                """
            )
            return

        value, _ = await self.fetch_new_datapoint()
        percentage_change = self._get_percentage_change(self.previous_value, value)
        
        if percentage_change >= self.percentage_change_threshold * 100:
            logger.info(f"Trigerring report - Percentage change threshold reached ({percentage_change:.4f}%)")
            self.previous_value = value
            self.sync_event.set()
        else:
            logger.info(f"Not triggering report - Percentage change threshold not reached ({percentage_change:.4f}%)")
        
        self.is_sync_event_handled = True
        self.pair_handled_data = {
            'name': self._address_to_pair_name(event['address']), 'reserve0': reserve0, 'reserve1': reserve1
        }

    async def _log_loop(self, polling_interval=8):
        while True:
            logger.info("Listening Sync events...")
            if not self.is_initialized: await self.initialize_price()
            try:
                self.is_sync_event_handled = False
                self.pair_handled_data = None
                block_number = self.w3.eth.get_block_number()

                if block_number < self.from_block:
                    logger.info(f"Reorg detected, resetting from_block ({self.from_block}) to {block_number - self.reorg_safe_default}")
                    self.from_block = block_number - self.reorg_safe_default

                event_filters = [
                    {
                        "fromBlock": self.from_block,
                        "toBlock": block_number,
                        "address": lp_contract.address,
                        "topics": [Web3.keccak(text="Sync(uint112,uint112)").hex()],
                    } for lp_contract in self.lps_contracts
                ]

                for event_filter in event_filters:
                    events = self.w3.eth.get_logs(event_filter)

                    for event in events:
                        await self._handle_event(event)

                self.from_block = block_number
                await self._check_time_limit()
                await asyncio.sleep(polling_interval)
            except Exception as e:
                logger.error(f"Error in log loop: {e}")

    def initialize_log_loop_thread(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            asyncio.run_coroutine_threadsafe(self._log_loop(), loop)
            loop.run_forever()
        except Exception as e:
            logger.error(f"Error in initialize_log_loop_thread: {e}")

    def listen_sync_events(self):
        th = threading.Thread(target=self.initialize_log_loop_thread, daemon=True)
        th.start()
        logger.info("Started listening to LP Sync contract events")