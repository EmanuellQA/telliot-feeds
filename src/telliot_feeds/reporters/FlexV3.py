from web3 import Web3
from eth_abi import encode_abi
from eth_abi.abi import encode_single
from eth_abi.packed import encode_single_packed

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
    ADDRESS = "0xc1EeD9232A0A44c2463ACB83698c162966FBc78d"

    def __init__(self) -> None:
        self.provider_url = "http://0.0.0.0:8545"
        self.w3 = Web3(Web3.HTTPProvider(self.provider_url))
        self.account = self.w3.eth.account.from_key("0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d")

    def _get_contract(self):
        return self.w3.eth.contract(address=self.ADDRESS, abi=self.ABI)

class FlexV3(Contract):
    def __init__(self) -> None:
        super().__init__()
        self.flexv3_contract = self._get_contract()

    def getNewValueCountbyQueryId(self, query_id):
        return self.flexv3_contract.functions.getNewValueCountbyQueryId(query_id).call()
    
    def _get_queryId(self, query_type: str, asset: str, currency: str):
        encoded_params = encode_abi(['string', 'string'], [asset, currency])
        query_data = encode_abi(["string", "bytes"], [query_type, encoded_params])
        query_id = bytes(Web3.keccak(query_data)).hex()
        return query_data, query_id
    
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
        gas_limit = transaction.estimateGas({"from": self.account.address})
        account_address = Web3.toChecksumAddress(self.account.address)
        tx_dict = {
            "from": account_address,
            "nonce": self.w3.eth.get_transaction_count(account_address),
            "gas": gas_limit,
            "gasPrice": self.w3.toWei(self.fetch_gas_price(), "gwei"),
        }
        built_tx = transaction.buildTransaction(tx_dict)
        acc = self.w3.eth.account.from_key(self.account.key)
        tx_signed = acc.sign_transaction(built_tx)
        tx_hash = self.w3.eth.send_raw_transaction(tx_signed.rawTransaction)
        tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=360)
        return tx_receipt
        
    def callSubmitValue(self):
        query_data, query_id = self._get_queryId('SpotPrice', 'pls', 'usd')
        print(f"0x{query_id}" == "0x1f984b2c7cbcb7f024e5bdd873d8ca5d64e8696ff219ebede2374bf3217c9b75")
        report_count = self.getNewValueCountbyQueryId(query_id)
        print(f'Report count: {report_count}')

        ARBITRARY_VALUE = 0.38
        value_to_wei = self.w3.toWei(ARBITRARY_VALUE, 'ether')

        tx_receipt = self.submitValue(
            value=encode_single('uint256', value_to_wei),
            nonce=report_count,
            queryData=query_data
        )
        tx_hash = tx_receipt['transactionHash'].hex()
        print(f"Report tx hash: {tx_hash}")

flexV3 = FlexV3()
flexV3.callSubmitValue()