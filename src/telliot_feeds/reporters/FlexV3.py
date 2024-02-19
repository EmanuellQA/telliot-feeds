import os
from collections.abc import Callable
import math

from concurrent.futures import ThreadPoolExecutor

import requests
from web3 import Web3
from telliot_core.utils.key_helpers import lazy_unlock_account
from telliot_feeds.datafeed import DataFeed
from chained_accounts import ChainedAccount
from telliot_core.contract.contract import Contract
from telliot_core.model.endpoints import RPCEndpoint
from telliot_feeds.utils.log import get_logger
from dotenv import load_dotenv

load_dotenv()

logger = get_logger(__name__)

class Contract:
    ABI = """
    [
    {
      "inputs": [
        {
          "internalType": "bytes32",
          "name": "_queryId",
          "type": "bytes32"
        }
      ],
      "name": "getNewValueCountbyQueryId",
      "outputs": [
        {
          "internalType": "uint256",
          "name": "",
          "type": "uint256"
        }
      ],
      "stateMutability": "view",
      "type": "function"
    },
    {
      "inputs": [
        {
          "internalType": "bytes32",
          "name": "_queryId",
          "type": "bytes32"
        },
        {
          "internalType": "bytes",
          "name": "_value",
          "type": "bytes"
        },
        {
          "internalType": "uint256",
          "name": "_nonce",
          "type": "uint256"
        },
        {
          "internalType": "bytes",
          "name": "_queryData",
          "type": "bytes"
        }
      ],
      "name": "submitValue",
      "outputs": [],
      "stateMutability": "nonpayable",
      "type": "function"
    }
    ]
    """
    ADDRESS = os.getenv("FETCH_FLEX_V3_ADDRESS")

    def __init__(self, endpoint_url: str):
        self.provider_url = endpoint_url
        self.w3 = Web3(Web3.HTTPProvider(self.provider_url))

    def _get_contract(self, address: str):
        return self.w3.eth.contract(address=address, abi=self.ABI)

class FlexV3(Contract):
    PRICE_SERVICE_BASE_URL = os.getenv('PRICE_SERVICE_BASE_URL', 'http://127.0.0.1:3333')

    def __init__(
      self,
      datafeed: DataFeed,
      endpoint: RPCEndpoint,
      account: ChainedAccount,
      chain_id: int, 
      get_fees: Callable,
      oracle: Contract
    ):
        super().__init__(endpoint.url)
        self.datafeed = datafeed
        self.endpoint = endpoint
        self.account = account
        self.chain_id = chain_id
        self.get_fees = get_fees
        self.oracle = oracle
        self.flexv3_contract = self._get_contract(self.oracle.address)
        self.absolute_tolerance = float(os.getenv("PRICE_DIFF_ABSOLUTE_TOLERANCE", 1e-2))

    def _send_request(self, url: str) -> requests.Response:
        try:
            response = self.session.get(url)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            logger.error(f"Error fetching data from {url}: {e}\n{e.response.text}")

    def _is_price_valid(self, value: float):
        try:
            self.session = requests.Session()

            requests_urls = [
                f'{self.PRICE_SERVICE_BASE_URL}/coingecko',
                f'{self.PRICE_SERVICE_BASE_URL}/coinpaprika',
                f'{self.PRICE_SERVICE_BASE_URL}/coinmarketcap',
                f'{self.PRICE_SERVICE_BASE_URL}/liquidity-pool/vwap',
            ]

            with ThreadPoolExecutor(max_workers=len(requests_urls)) as executor:
                responses = list(executor.map(self._send_request, requests_urls))

            successful_responses = [response for response in responses if response is not None]

            green_color = '\033[92m'
            endc_color = '\033[0m'

            logger.info(f"{green_color}Price Service API responses: {[r.json()['service'] for r in successful_responses]}{endc_color}")

            for response in successful_responses:
                request_url = response.url
                data = response.json()
                service_name = data['service']
                price = data['price']

                is_close = math.isclose(value, price, abs_tol=self.absolute_tolerance)
                if is_close: break

            
            logger.info(f"""
                {green_color}
                Price Service API info:
                Request URL: {request_url}
                Service name: {service_name}
                API Price: {price}
                Telliot Price: {value}
                Abs Diff: {abs(price - value)}
                Abs tolerance: {self.absolute_tolerance}
                Is close? {is_close}
                {endc_color}
            """)
            return is_close
        except Exception as e:
            logger.warning(f"Error validating price with Price Service API: {e}")
        finally:
            self.session.close()
            return True

    async def fetch_new_datapoint(self):
        try:
          await self.datafeed.source.fetch_new_datapoint()
          latest_data = self.datafeed.source.latest
          if latest_data[0] is None: raise Exception("Unable to retrieve updated datafeed value.")
          
          logger.info(f"Current query: {self.datafeed.query.descriptor}")
          query = self.datafeed.query
          try:
              value = query.value_type.encode(latest_data[0])
              logger.debug(f"Value: {latest_data[0]} - Encoded value: {value.hex()}")
          except Exception as e:
              raise Exception(f"Error encoding response value {latest_data[0]} - {e}")

          return latest_data[0], value
        except Exception as e:
            logger.error(f"Error fetching new datapoint: {e}")
            return None, None

    def getNewValueCountbyQueryId(self, query_id):
        return self.flexv3_contract.functions.getNewValueCountbyQueryId(query_id).call()
    
    def fetch_gas_price(self) -> float:
        priceGwei = self.w3.fromWei(self.w3.eth.gas_price, "gwei")
        return float(priceGwei) * 1.4

    def submitValue(self, value, nonce, queryData, queryId):
        contract_function = self.flexv3_contract.get_function_by_name('submitValue')
        transaction = contract_function(
            _queryId=queryId,
            _value=value,
            _nonce=nonce,
            _queryData=queryData
        )
        logger.info(f"""
            Submitting value to Flex V3 contract:
            value: {value.hex()}
            nonce: {nonce}
            _queryId: {queryId.hex()}
        """)
        account_address = Web3.toChecksumAddress(self.account.address)
        logger.info("Estimating gas limit")
        gas_limit = transaction.estimateGas({"from": account_address})

        priority_fee, max_fee = self.get_fees()
        tx_dict = {
            "from": account_address,
            "nonce": self.w3.eth.get_transaction_count(account_address),
            "gas": gas_limit,
            "maxFeePerGas": self.w3.toWei(max_fee, "gwei"),
            "maxPriorityFeePerGas": self.w3.toWei(priority_fee, "gwei"),
            "chainId": self.chain_id,
        }
        built_tx = transaction.buildTransaction(tx_dict)

        logger.info(f"""
            Transaction info:
            from: {built_tx['from']}
            nonce: {built_tx['nonce']}
            gas_limit: {built_tx['gas']}
            maxFeePerGas: {built_tx['maxFeePerGas']}
            maxPriorityFeePerGas: {built_tx['maxPriorityFeePerGas']}
            chainId: {built_tx['chainId']}
        """)

        lazy_unlock_account(self.account)
        local_account = self.account.local_account
        tx_signed = local_account.sign_transaction(built_tx)
        logger.info("Sending submitValue transaction")
        tx_hash = self.w3.eth.send_raw_transaction(tx_signed.rawTransaction)
        tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=360)
        if tx_receipt["status"] == 0:
            logger.error(tx_receipt)
            raise Exception(f"Transaction reverted. ({tx_hash.hex()})\nFailed to confirm transaction\n{tx_receipt}")
        return tx_receipt
        
    async def callSubmitValue(self):
        logger.info("Calling Submit Value")
        try:
          query_id = self.datafeed.query.query_id
          query_data = self.datafeed.query.query_data

          report_count = self.getNewValueCountbyQueryId(query_id)
          logger.info(f'Report count: {report_count} (query_id: {query_id.hex()})')

          value, value_enconded = await self.fetch_new_datapoint()

          if not self._is_price_valid(value):
            raise Exception(f"Datafeed value {value} is not close to coingecko pls price")

          tx_receipt = self.submitValue(
              value=value_enconded,
              nonce=report_count,
              queryData=query_data,
              queryId=query_id
          )
          tx_hash = tx_receipt['transactionHash'].hex()
          tx_url = f"{self.endpoint.explorer}/tx/{tx_hash}"
          logger.info(f"View reported data: \n{tx_url}")
          return tx_hash
        except Exception as e:
            logger.error(f"Error submitting report: {e}")
            return None
