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
    ADDRESS = "0xE56043671df55dE5CDf8459710433C10324DE0aE"

    def __init__(self):
        self.provider_url = os.getenv('LP_PULSE_NETWORK_URL', 'https://rpc.pulsechain.com')
        self.w3 = Web3(Web3.HTTPProvider(self.provider_url))

    def _get_contract(self):
        return self.w3.eth.contract(address=self.ADDRESS, abi=self.ABI)

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
        super().__init__()
        self.lp_contract = self._get_contract()
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

    def _check_time_limit(self):
        if time.time() - self.current_report_time['timestamp'] > self.time_limit:
            logger.info("Time limit reached, setting time limit event")
            self.time_limit_event.set()
            self.sync_event.set()

    async def _log_loop(self, event_filter, polling_interval=8):
        while True:
            for event in event_filter.get_new_entries():
                logger.info(f"""
                    LP Sync event received:
                    reserve0: {event['args']['reserve0']}
                    reserve1: {event['args']['reserve1']}
                """)

                value, _ = await self.fetch_new_datapoint()
                percentage_change = self._get_percentage_change(self.previous_value, value)
                
                if percentage_change >= self.percentage_change_threshold:
                    logger.info("Trigerring report - Percentage change threshold reached")
                    self.sync_event.set()
                    self.previous_value = value
                else:
                    logger.info(f"Not triggering report - Percentage change threshold not reached ({percentage_change:.2f}%)")
            time.sleep(polling_interval)
            self._check_time_limit()
    
    def initialize_log_loop_thread(self, event_filter):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._log_loop(event_filter))
        loop.close()

    def listen_sync_events(self):
        event_filter = self.lp_contract.events.Sync.createFilter(fromBlock='latest')
        th = threading.Thread(target=self.initialize_log_loop_thread, args=(event_filter,), daemon=True)
        th.start()
        logger.info("Started listening to LP Sync contract events")