import os
from collections.abc import Callable
import logging
from logging.handlers import RotatingFileHandler
import time
import asyncio
import threading
from web3 import Web3
from dotenv import load_dotenv

load_dotenv()

def get_logger(logger_name: str):
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter(f'\033[92m%(name)s - %(levelname)s - %(message)s\033[0m')
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    rotating_file_handler = RotatingFileHandler(
        filename=f'{logger_name}.log',
        maxBytes=10000000,
        backupCount=5
    )
    rotating_file_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    logger.addHandler(rotating_file_handler)
    return logger

logger = get_logger('ListenLPContract')

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
    DAI_ADDRESS = "0xE56043671df55dE5CDf8459710433C10324DE0aE"
    USDT_ADDRESS = "0x322Df7921F28F1146Cdf62aFdaC0D6bC0Ab80711"
    USDC_ADDRESS = "0x6753560538ECa67617A9Ce605178F788bE7E524E"

    def __init__(self, endpoint_url: str):
        self.provider_url = endpoint_url
        self.w3 = Web3(Web3.HTTPProvider(self.provider_url))

    def _get_contract(self, LP_pair: str):
        address = getattr(self, f"{LP_pair}_ADDRESS")
        return self.w3.eth.contract(address=address, abi=self.ABI)

class ListenLPContract(Contract):
    def __init__(
            self,
            sync_event: threading.Event,
            time_limit_event: threading.Event,
            current_report_time: dict[str,int],
            fetch_new_datapoint: Callable,
            time_limit:int=3600,
            percentage_change_threshold:float=0.5
    ):
        super().__init__(os.getenv('LP_PULSE_NETWORK_URL', 'https://rpc.pulsechain.com'))
        self.dai_lp_contract = self._get_contract('DAI')
        self.usdc_lp_contract = self._get_contract('USDC')
        self.usdt_lp_contract = self._get_contract('USDT')
        self.sync_event = sync_event
        self.time_limit_event = time_limit_event
        self.current_report_time = current_report_time
        self.time_limit = time_limit
        self.percentage_change_threshold = percentage_change_threshold
        self.fetch_new_datapoint = fetch_new_datapoint
    
    async def initialize_price(self):
        logger.info("Initializing value")
        value, _ = await self.fetch_new_datapoint()
        self.previous_value = value

    def _get_percentage_change(self, previous_value, value):
        percentage_change = ((value - previous_value) / previous_value) * 100
        return abs(percentage_change)

    async def _check_time_limit(self):
        time_elapsed = time.time() - self.current_report_time['timestamp']
        if time_elapsed > self.time_limit:
            if not self.time_limit_event.is_set():
                logger.info(f"Time limit reached, setting time limit event (time elapsed={time_elapsed:.2f}, time limit={self.time_limit})")
                value, _ = await self.fetch_new_datapoint()
                self.previous_value = value
                self.time_limit_event.set()
                self.sync_event.set()

    def _address_to_pair_name(self, lp_address: str):
        if lp_address == self.DAI_ADDRESS: return "WPLS/DAI"
        if lp_address == self.USDC_ADDRESS: return "USDC/WPLS"
        if lp_address == self.USDT_ADDRESS: return "USDT/WPLS"

    async def _handle_event(self, event):
        logger.info(f"""
            LP Sync event received:
            address: {event['address']}
            Pair: {self._address_to_pair_name(event['address'])}
            reserve0: {event['args']['reserve0']}
            reserve1: {event['args']['reserve1']}
        """)

        value, _ = await self.fetch_new_datapoint()
        percentage_change = self._get_percentage_change(self.previous_value, value)
        
        if percentage_change >= self.percentage_change_threshold:
            logger.info(f"Trigerring report - Percentage change threshold reached ({percentage_change:.2f}%)")
            self.previous_value = value
            self.sync_event.set()
        else:
            logger.info(f"Not triggering report - Percentage change threshold not reached ({percentage_change:.2f}%)")

    async def _log_loop(self, dai_event_filter, usdc_event_filter, usdt_event_filter, polling_interval=8):
        while True:
            try:
                has_sync_event = False
                for event in dai_event_filter.get_new_entries():
                    has_sync_event = True
                    await self._handle_event(event)

                if has_sync_event: continue
                for event in usdt_event_filter.get_new_entries():
                    has_sync_event = True
                    await self._handle_event(event)

                if has_sync_event: continue
                for event in usdc_event_filter.get_new_entries():
                    has_sync_event = True
                    await self._handle_event(event)

                await self._check_time_limit()    
                time.sleep(polling_interval)
            except Exception as e:
                logger.error(f"Error in log loop: {e}")

    def initialize_log_loop_thread(self, dai_event_filter, usdc_event_filter, usdt_event_filter):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._log_loop(dai_event_filter, usdc_event_filter, usdt_event_filter))
        loop.close()

    def listen_sync_events(self):
        dai_event_filter = self.dai_lp_contract.events.Sync.createFilter(fromBlock='latest')
        usdc_event_filter = self.usdc_lp_contract.events.Sync.createFilter(fromBlock='latest')
        usdt_event_filter = self.usdt_lp_contract.events.Sync.createFilter(fromBlock='latest')
        th = threading.Thread(
            target=self.initialize_log_loop_thread,
            args=(dai_event_filter, usdc_event_filter, usdt_event_filter),
            daemon=True
        )
        th.start()
        logger.info("Started listening to LP Sync contract events")