import os
import logging
from logging.handlers import RotatingFileHandler

from web3 import Web3
from telliot_core.utils.key_helpers import lazy_unlock_account
from telliot_feeds.datafeed import DataFeed
from chained_accounts import ChainedAccount
from telliot_core.model.endpoints import RPCEndpoint
from dotenv import load_dotenv

load_dotenv()

def get_logger(logger_name: str):
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter(f'\033[94m%(name)s - %(levelname)s - %(message)s\033[0m')
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

logger = get_logger('FlexV3')

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

    def __init__(self):
        self.provider_url = "http://0.0.0.0:8545"
        self.w3 = Web3(Web3.HTTPProvider(self.provider_url))

    def _get_contract(self):
        return self.w3.eth.contract(address=self.ADDRESS, abi=self.ABI)

class FlexV3(Contract):
    def __init__(self, datafeed: DataFeed, endpoint: RPCEndpoint, account: ChainedAccount):
        super().__init__()
        self.datafeed = datafeed
        self.endpoint = endpoint
        print(self.endpoint)
        print(dir(self.endpoint))
        print(self.endpoint.url)
        self.account = account
        self.flexv3_contract = self._get_contract()

    async def fetch_new_datapoint(self):
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

    def getNewValueCountbyQueryId(self, query_id):
        return self.flexv3_contract.functions.getNewValueCountbyQueryId(query_id).call()
    
    def fetch_gas_price(self) -> float:
        priceGwei = self.w3.fromWei(self.w3.eth.gas_price, "gwei")
        return float(priceGwei) * 1.4

    def submitValue(self, value, nonce, queryData):
        contract_function = self.flexv3_contract.get_function_by_name('submitValue')
        transaction = contract_function(
            _value=value,
            _nonce=nonce,
            _queryData=queryData
        )
        account_address = Web3.toChecksumAddress(self.account.address)
        gas_limit = transaction.estimateGas({"from": account_address})
        tx_dict = {
            "from": account_address,
            "nonce": self.w3.eth.get_transaction_count(account_address),
            "gas": gas_limit,
            "gasPrice": self.w3.toWei(self.fetch_gas_price(), "gwei"),
        }
        built_tx = transaction.buildTransaction(tx_dict)

        lazy_unlock_account(self.account)
        local_account = self.account.local_account
        tx_signed = local_account.sign_transaction(built_tx)
        tx_hash = self.w3.eth.send_raw_transaction(tx_signed.rawTransaction)
        tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=360)
        return tx_receipt
        
    async def callSubmitValue(self):
        logger.info("Calling Submit Value")
        try:
          query_id = self.datafeed.query.query_id
          query_data = self.datafeed.query.query_data

          report_count = self.getNewValueCountbyQueryId(query_id)
          logger.info(f'Report count: {report_count}')

          _, value_enconded = await self.fetch_new_datapoint()

          tx_receipt = self.submitValue(
              value=value_enconded,
              nonce=report_count,
              queryData=query_data
          )
          tx_hash = tx_receipt['transactionHash'].hex()
          tx_url = f"{self.endpoint.explorer}/tx/{tx_hash}"
          logger.info(f"View reported data: \n{tx_url}")
          return tx_hash
        except Exception as e:
            logger.error(f"Error submitting report: {e}")
            return None
