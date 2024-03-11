import os
import signal
import sys
import logging
import pexpect
import subprocess
import argparse
from argparse import RawTextHelpFormatter
from pathlib import Path
from decimal import *
from web3 import Web3
from eth_abi import encode_abi
from telliot_core.directory import contract_directory
import re
import time

MOCK_PRICE_API_PORT=3001

logger = logging.getLogger('telliot_e2e_tests')
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(levelname)s | %(name)s | %(message)s")
ch.setFormatter(formatter)
logger.addHandler(ch)

class Contract:
    def __init__(self, oracle_address: str, provider_url: str = "https://rpc.v4.testnet.pulsechain.com"):
        # TODO parameterize these
        self.oracle_address = oracle_address
        self.provider_url = provider_url
        self.oracle = None
        self.provider = None

    def initialize(self):
        try:
            w3 = Web3(Web3.HTTPProvider(self.provider_url))

            abi = """
            [
            {
                "inputs": [
                {
                    "internalType": "bytes32",
                    "name": "_queryId",
                    "type": "bytes32"
                }
                ],
                "name": "getCurrentValue",
                "outputs": [
                {
                    "internalType": "bytes",
                    "name": "_value",
                    "type": "bytes"
                }
                ],
                "stateMutability": "view",
                "type": "function"
            },
            {
            "inputs": [
                {
                "internalType": "address",
                "name": "_reporter",
                "type": "address"
                }
            ],
            "name": "getReporterLastTimestamp",
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
                "internalType": "address",
                "name": "_manager",
                "type": "address"
                },
                {
                "internalType": "bytes",
                "name": "_config",
                "type": "bytes"
                }
            ],
            "name": "setupManagedQuery",
            "outputs": [],
            "stateMutability": "nonpayable",
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
                "internalType": "address",
                "name": "_reporter",
                "type": "address"
                }
            ],
            "name": "addReporter",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function"
            }
            ]
            """
            self.provider = w3
            self.oracle = w3.eth.contract(address=self.oracle_address, abi=abi)
            logger.info(f'Oracle contract at address {self.oracle_address} initialized')
        except Exception as e:
            logger.error("Oracle contract initialization error:")
            logger.error(e)

    @staticmethod
    def create(oracle_address: str, provider_url: str):
        instance = Contract(oracle_address, provider_url)
        instance.initialize()
        return instance

    def _bytes_to_decimal(self, bytes: bytes) -> Decimal:
        decoded_value = int.from_bytes(bytes, byteorder='big')
        formatted_value = f'{(decoded_value / 1e18):.18f}'
        return Decimal(formatted_value)

    def get_current_value_as_decimal(self, queryId: str):
        current_value: bytes = self.oracle.functions.getCurrentValue(
            queryId).call()
        return self._bytes_to_decimal(current_value)
    
    def get_reporter_last_timestamp(self, reporter: str) -> int:
        report_checksum_address = self.provider.toChecksumAddress(reporter)
        last_timestamp: int = self.oracle.functions.getReporterLastTimestamp(report_checksum_address).call()
        return last_timestamp

def _get_new_price(price: Decimal) -> Decimal:
    return (price * Decimal('1')).quantize(Decimal('1e-18'))

def get_mock_price_path() -> Path:
    current_dir = Path(__file__).parent.absolute()
    mock_price_path = current_dir.parent.absolute() / 'mock-price-api'
    return (mock_price_path)

def configure_mock_price_api_env(new_price: Decimal, env_config: list[str] = None) -> None:
    env_file = get_mock_price_path() / '.env'

    if env_config != None:
      with open(env_file, 'w') as file:
          file.write("".join(env_config))
      logger.info(f"Mock Price API original env configuration restored")
      return []

    prevLines = []
    if env_file.exists():
        with open(env_file, 'r') as file:
            prevLines = file.readlines()
            prevLines = [line if line.endswith('\n') else line + '\n' for line in prevLines]
    lines = prevLines.copy()
    lines += [f'SERVER_PORT={MOCK_PRICE_API_PORT}\n', f'PLS_PRICE={new_price}\n', 'PULSECHAIN_NODE_URL=http://localhost:8545']
    with open(env_file, 'w') as file:
        file.write("".join(lines))
    return prevLines

def initialize_mock_price_api() -> subprocess.Popen:
    current_dir = Path(__file__).parent.absolute()
    mock_price_path = get_mock_price_path()

    os.chdir(mock_price_path)
    process = subprocess.Popen(['npm', 'start'], preexec_fn=os.setsid)
    os.chdir(current_dir)

    return process

def switch_mock_price_git_branch(branch_name: str) -> None:
    current_dir = Path(__file__).parent.absolute()
    mock_price_path = get_mock_price_path()

    os.chdir(mock_price_path)
    branches = subprocess.run(['git', 'branch', '-a'], capture_output=True, text=True)
    if branch_name not in branches.stdout:
        logger.error(f"Branch {branch_name} does not exist in mock-price-api")
        sys.exit(1)

    subprocess.run(['git', 'checkout', branch_name])
    os.chdir(current_dir)

    print(f"Mock Price API git branch switched to {branch_name}")

def _configure_telliot_env_with_mock_price(env_config: list[str] = None) -> list[str]:
    current_dir = Path(__file__).parent.absolute()
    telliot_path = current_dir.parent.absolute() / 'telliot-feeds'
    env_file = telliot_path / '.env'

    logger.debug(f"path for the .env file:{env_file}")

    if env_config != None:
        with open(env_file, 'w') as file:
            file.write("".join(env_config))
        logger.info(f"TELLIOT original env configuration restored")
        return []

    prev_env_config = []
    env_file = telliot_path / '.env'
    if env_file.exists():
        with open(env_file, 'r') as file:
            prev_env_config = file.readlines()
            prev_env_config = [line if line.endswith('\n') else line + '\n' for line in prev_env_config]
        logger.info("TELLIOT original env configuration saved")
    with open(env_file, 'w') as file:
        file.write(f"COINGECKO_MOCK_URL=http://localhost:{MOCK_PRICE_API_PORT}/coingecko")
    logger.info(f"TELLIOT env configuration updated")
    logger.info(f"Waiting 3s for file sync to the disk")

    logger.debug(f"begin of .env file content:")
    if env_file.exists():
        with open(env_file, 'r') as file:
            config_content = file.readlines()
            logger.debug("\n".join(config_content))
    logger.debug(f"end of .env file content:")
    time.sleep(3)

    return prev_env_config

def submit_report_with_telliot(account_name: str, stake_amount: str, managed_feeds: bool = False) -> str:
    report_hash = ""
    try:
        report = f'telliot report -a {account_name} -ncr -qt pls-usd-spot --fetch-flex --submit-once -s {stake_amount} -mf 80000 -pf 1.5 -gm 20'

        if managed_feeds:
            report = f'telliot report -a {account_name} -ncr -qt validated-feed-usd-spot-api --fetch-flex --submit-once -mf 80000 -pf 1.5 -gm 20'

        logger.info(f"Submitting report: {report}")
        report_process = pexpect.spawn(report, timeout=120)
        report_process.logfile = sys.stdout.buffer
        report_process.expect("\w+\r\n")
        report_process.expect("\w+\r\n")
        report_process.expect("\w+\r\n")
        if managed_feeds:
            report_process.expect("\w+\r\n")
        report_process.sendline('y')
        report_process.expect("\w+\r\n")
        report_process.sendline('')
        report_process.expect("\w+\r\n")
        report_process.sendline('')
        report_process.expect("\w+\r\n")
        report_process.sendline('')
        report_process.expect("confirm settings.")
        report_process.sendline('\n')
        report_process.expect(pexpect.EOF)
        report_process.close()
        logger.info("Submit report with telliot OK")

        report_log = report_process.before.decode('utf-8')
        regexp = r'View reported data:\s+\n(http[s]?://[^/]+[\/]?/tx/\w+)'

        tx_hash = re.search(
            regexp,
            report_log
        )

        if not tx_hash:
            logger.warning("No 'View reported data:' found in telliot report log")
            return None

        report_hash = re.search(r'^.*/tx/(\w+)$', tx_hash.group(1)).group(1)
        logger.info(f"Report hash: {report_hash}")
    except Exception as e:
        logger.error("Submit report with telliot error:")
        logger.error(e)
    finally:
        return report_hash

def write_price_to_file(price: Decimal, hash: str) -> None:
    path = Path(__file__).parent.absolute() / 'current_price.json'
    with open(path, 'w') as file:
      file.write(f'{{"current_price": {price}, "hash": "{hash}"}}')
    logger.info(f"Current price written to file {path}")

def write_managed_feeds_report_to_file(report_hash: str, queryId: str, timestamp: str) -> None:
    path = Path(__file__).parent.absolute() / 'managed_feeds_report.json'
    with open(path, 'w') as file:
      file.write(f'{{"report_hash": "{report_hash}", "queryId": "{queryId}", "timestamp": "{timestamp}"}}')
    logger.info(f"Managed feeds report written to file {path}")

def _setup_managed_query(queryId: str, address: str, requiresStaking: bool, contract: Contract) -> None:
    config = encode_abi(['bool'], [requiresStaking])

    address = contract.provider.toChecksumAddress(address)
    
    try:
        contract.oracle.functions.setupManagedQuery(
            Web3.toBytes(hexstr=queryId),
            address,
            config
        ).transact({'from': address})
        logger.info(f"Managed query {queryId} setup OK")
    except Exception as e:
        logger.error(f"Managed query {queryId} setup error:")
        logger.error(e)

def _add_reporter(queryId: str, address: str, contract: Contract) -> None:
    address = Web3.toChecksumAddress(address)
    try:
        contract.oracle.functions.addReporter(
            Web3.toBytes(hexstr=queryId),
            address
        ).transact({'from': address})
        logger.info(f"Reporter {address} added to query {queryId} OK")
    except Exception as e:
        logger.error(f"Reporter {address} added to query {queryId} error:")
        logger.error(e)

def handle_managed_feeds_mode(oracle_address: str, provider_url: str, account_name: str) -> None:
    managed_feed_queryId = "0x1f984b2c7cbcb7f024e5bdd873d8ca5d64e8696ff219ebede2374bf3217c9b75"

    account_find = f'telliot account find --name {account_name}'
    account_process = pexpect.spawn(account_find, timeout=120)
    account_process.logfile = sys.stdout.buffer
    account_process.expect(pexpect.EOF)

    account_log = account_process.before.decode('utf-8')

    account_address = re.search(
        fr'Account name: {account_name}, address: (0x\w+), chain IDs: \[\d+\]',
        account_log
    )
    account_address = account_address.group(1)
    logger.info(f"Account address: {account_address}")

    contract = Contract.create(
        oracle_address=oracle_address,
        provider_url=provider_url
    )

    _setup_managed_query(
        queryId=managed_feed_queryId,
        address=account_address,
        requiresStaking=False,
        contract=contract
    )

    _add_reporter(
        queryId=managed_feed_queryId,
        address=account_address,
        contract=contract
    )

    report_hash = submit_report_with_telliot(account_name=account_name, stake_amount="None", managed_feeds=True)

    if not report_hash:
        logger.error("Submit managed-feeds report with telliot error")
    assert report_hash, "Submit managed-feeds report with telliot error"

    lastTimestamp = contract.get_reporter_last_timestamp(account_address)

    write_managed_feeds_report_to_file(report_hash, managed_feed_queryId, lastTimestamp)

def main():
    parser = argparse.ArgumentParser(
        description="Telliot submit price E2E test",
        formatter_class=RawTextHelpFormatter
    )
    parser.add_argument(
        '-a',
        '--account',
        type=str,
        required=True,
        help=('Account name to be used in the telliot 2e2 test.\n'
        'You can get accounts by running the following command\n'
        '"telliot account find"')
    )
    parser.add_argument(
        '-s',
        '--stake',
        type=str,
        required=True,
        help=('Stake amount to submit a report.\n'
        'The minimum stake amount depends on the the FetchFlex deployment\n'
        'Please refer monorepo/fetch-contracts and fetchFlex.sol contract')
    )
    parser.add_argument(
        '-chain',
        '--chain-id',
        type=int,
        choices=[943, 369],
        required=True,
        help=('Telliot environment to use, choices = %(choices)s\n'
        'The "default" env will configure telliot-core to use contract_directory.json\n'
        'instead of contract_directory.<ENV_NAME>.json.'),
        default='943'
    )
    parser.add_argument(
        '-p',
        '--provider-url',
        type=str,
        required=False,
        help=('Provider url to use for the Oracle contract.\n'
        'Default is https://rpc.v4.testnet.pulsechain.com'),
        default='https://rpc.v4.testnet.pulsechain.com'
    )
    parser.add_argument(
        '-m',
        '--managed-feeds',
        type=bool,
        required=False,
        help=('Managed feeds mode to use for the Oracle contract.\n'
        'Default is False'),
        default=False,
        action=argparse.BooleanOptionalAction
    )

    args = parser.parse_args()

    account_name = args.account
    stake_amount = args.stake
    chain_id = args.chain_id
    provider_url = args.provider_url
    managed_feeds_mode = args.managed_feeds

    contract = contract_directory.find(chain_id=chain_id, name="fetchflex-oracle")[0]
    oracle_address = contract.address[chain_id]

    logger.info(f"""
        Starting E2E test for telliot submit price, config:
        account name: {account_name}
        stake amount: {stake_amount}
        chain id: {chain_id}
        provider url: {provider_url}
        oracle address: {oracle_address}
        managed feeds mode: {managed_feeds_mode}
    """)

    if managed_feeds_mode:
        try:
            logger.info("Managed feeds mode is enabled")
            mock_price_env = configure_mock_price_api_env('0.000062')
            mock_price_ps = initialize_mock_price_api()
            prev_env_config = _configure_telliot_env_with_mock_price()
            handle_managed_feeds_mode(oracle_address, provider_url, account_name)
            _configure_telliot_env_with_mock_price(prev_env_config)
        except Exception as e:
            logger.error("Managed feeds report error:")
            logger.error(e)
        finally:
            os.killpg(os.getpgid(mock_price_ps.pid), signal.SIGTERM)
            return

    mock_price_env = configure_mock_price_api_env('0.000062')
    mock_price_ps = initialize_mock_price_api()

    # first report to avoid "transaction reverted" error (when using ganache, see mock-deployment.sh in monorepo/e2e_tests folder)
    # todo update mock to use anvil -> no need to submit a report before
    prev_env_config = _configure_telliot_env_with_mock_price()
    report_hash1 = submit_report_with_telliot(account_name=account_name, stake_amount=stake_amount)
    
    try:
        report_hash2 = submit_report_with_telliot(account_name=account_name, stake_amount=stake_amount)
        _configure_telliot_env_with_mock_price(prev_env_config)
    except Exception as e:
        logger.error("Submit report with telliot error:")
        logger.error(e)
    finally:
        configure_mock_price_api_env(0, mock_price_env)
        os.killpg(os.getpgid(mock_price_ps.pid), signal.SIGTERM)

    contract = Contract.create(
        oracle_address=oracle_address,
        provider_url=provider_url
    )
    queryId = "0x83245f6a6a2f6458558a706270fbcc35ac3a81917602c1313d3bfa998dcc2d4b"

    price: Decimal = contract.get_current_value_as_decimal(queryId)
    logger.info(f"Price for {queryId} is {price} USD")

    new_price: Decimal = _get_new_price(price)
    mock_price_env = configure_mock_price_api_env(new_price)
    mock_price_ps = initialize_mock_price_api()
    logger.info(f"MOCK_PRICE_API initialized with price {new_price}")

    # todo, stake * 10 is not enough, needs to set REPORT_LOCK_TIME=1 to avoid lock time error
    prev_env_config = _configure_telliot_env_with_mock_price()
    report_hash3 = submit_report_with_telliot(account_name=account_name, stake_amount=str(int(stake_amount)*10))
    _configure_telliot_env_with_mock_price(prev_env_config)

    configure_mock_price_api_env(0, mock_price_env)

    price: Decimal = contract.get_current_value_as_decimal(queryId)
    logger.info(f"Price after report for {queryId} is {price} USD")
    try:
        assert abs(price - new_price) <= Decimal('1e-2')
        logger.info(f'OK - Submit price test passed (considering 2 decimals). Difference = {abs(price - new_price)}')

        report_hash = report_hash3 if report_hash3 else report_hash2 if report_hash2 else report_hash1
        write_price_to_file(price, report_hash)
    except AssertionError as e:
        logger.error(f'FAIL - Submit price test failed. Difference = {abs(price - new_price)}')
        logger.error(e)
    finally:
        os.killpg(os.getpgid(mock_price_ps.pid), signal.SIGTERM)
        switch_mock_price_git_branch('dev')

if __name__ == "__main__":
    main()