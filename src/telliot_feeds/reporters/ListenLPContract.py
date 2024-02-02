import os
from collections.abc import Callable
import logging
from logging.handlers import RotatingFileHandler
import time
import asyncio
import threading
from web3 import Web3
from eth_abi import decode_abi
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
        logger.info(f"Initializing LP contract with endpoint_url={endpoint_url}")
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
        self.from_block = self.w3.eth.get_block_number()
    
    async def initialize_price(self):
        logger.info("Initializing value")
        value, _ = await self.fetch_new_datapoint()
        self.previous_value = value
        logger.info(f"Initialized with value: {value}")

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
            return

        value, _ = await self.fetch_new_datapoint()
        percentage_change = self._get_percentage_change(self.previous_value, value)
        
        if percentage_change >= self.percentage_change_threshold:
            logger.info(f"Trigerring report - Percentage change threshold reached ({percentage_change:.2f}%)")
            self.previous_value = value
            self.sync_event.set()
        else:
            logger.info(f"Not triggering report - Percentage change threshold not reached ({percentage_change:.2f}%)")
        
        self.is_sync_event_handled = True

    async def _log_loop(self, polling_interval=8):
        while True:
            logger.info("Listening Sync events...")
            try:
                self.is_sync_event_handled = False
                block_number = self.w3.eth.get_block_number()

                event_filter_dai = {
                    "fromBlock": self.from_block,
                    "toBlock": block_number,
                    "address": self.dai_lp_contract.address,
                    "topics": [Web3.keccak(text="Sync(uint112,uint112)").hex()],
                } 

                event_filter_usdt = {
                    **event_filter_dai,
                    "address": self.usdt_lp_contract.address
                }

                event_filter_usdc = {
                    **event_filter_dai,
                    "address": self.usdc_lp_contract.address
                }

                events_dai = self.w3.eth.get_logs(event_filter_dai)
                events_usdt = self.w3.eth.get_logs(event_filter_usdt)
                events_usdc = self.w3.eth.get_logs(event_filter_usdc)
                
                for event in events_dai:
                    await self._handle_event(event)

                for event in events_usdt:
                    await self._handle_event(event)

                for event in events_usdc:
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