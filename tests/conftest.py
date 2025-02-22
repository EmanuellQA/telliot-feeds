"""Pytest Fixtures used for testing Pytelliot"""
import asyncio
import os

import pytest
import pytest_asyncio
from brownie import accounts
from brownie import Autopay
from brownie import chain
from brownie import multicall as brownie_multicall
from brownie import QueryDataStorage
from brownie import StakingToken
from brownie import FetchFlex
from brownie import FetchFlex360
from brownie import FetchXMasterMock
from brownie import FetchXOracleMock
from chained_accounts import ChainedAccount
from chained_accounts import find_accounts
from multicall import multicall
from multicall.constants import MULTICALL2_ADDRESSES
from multicall.constants import Network
from telliot_core.apps.core import TelliotCore
from telliot_core.apps.telliot_config import TelliotConfig
from web3 import Web3

from telliot_feeds.datasource import DataSource
from telliot_feeds.dtypes.datapoint import datetime_now_utc
from telliot_feeds.dtypes.datapoint import OptionalDataPoint
from telliot_feeds.reporters.fetch_flex import FetchFlexReporter

def get_gas_price():
    w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:8545"))
    return w3.eth.gas_price

gas_price = get_gas_price()
multiplier = 1.401
gas_price_with_multiplier = gas_price * multiplier
# it handles the error: "ValueError: max fee per gas less than block base fee"

@pytest.fixture(scope="module", autouse=True)
def shared_setup(module_isolation):
    pass


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module", autouse=True)
def mumbai_cfg():
    """Return a test telliot configuration for use on polygon-mumbai

    If environment variables are defined, they will override the values in config files
    """
    cfg = TelliotConfig()

    # Override configuration for rinkeby testnet
    cfg.main.chain_id = 943

    endpt = cfg.get_endpoint()
    if "INFURA_API_KEY" in endpt.url:
        endpt.url = f'https://polygon-mumbai.infura.io/v3/{os.environ["INFURA_API_KEY"]}'

    mumbai_accounts = find_accounts(chain_id=80001)
    if not mumbai_accounts:
        # Create a test account using PRIVATE_KEY defined on github.
        key = os.getenv("PRIVATE_KEY", None)
        if key:
            ChainedAccount.add(
                "git-mumbai-key",
                chains=80001,
                key=os.environ["PRIVATE_KEY"],
                password="",
            )
        else:
            raise Exception("Need a mumbai account")

    return cfg


class BadDataSource(DataSource[float]):
    """Source that does not return an updated DataPoint."""

    async def fetch_new_datapoint(self) -> OptionalDataPoint[float]:
        return None, None


@pytest.fixture(scope="module")
def bad_datasource():
    """Used for testing no updated value for datafeeds."""

    return BadDataSource()


class GoodFakeSource(DataSource[float]):
    """Source that does not return an updated DataPoint."""

    async def fetch_new_datapoint(self) -> OptionalDataPoint[float]:
        datapoint = (1234.0, datetime_now_utc())
        self.store_datapoint(datapoint)
        print("Guaranteed price source returning:", datapoint[0])
        return datapoint


@pytest.fixture(scope="module")
def guaranteed_price_source():
    """Used for testing no updated value for datafeeds."""
    return GoodFakeSource()


def local_node_cfg(chain_id: int):
    """Return a test telliot configuration for use of fetchFlex contracts. Overrides
    the default Web3 provider with a local Ganache endpoint.
    """

    cfg = TelliotConfig()

    # Use a chain_id with FetchFlex contracts deployed
    cfg.main.chain_id = chain_id

    endpt = cfg.get_endpoint()

    # Configure testing using local Ganache node
    endpt.url = "http://127.0.0.1:8545"

    # Advance block number to avoid assertion error in endpoint.connect():
    # connected = self._web3.eth.get_block_number() > 1
    chain.mine(10)

    accounts = find_accounts(chain_id=chain_id)
    if not accounts:
        # Create a test account using PRIVATE_KEY defined on github.
        key = os.getenv("PRIVATE_KEY", None)
        if key:
            ChainedAccount.add(
                "git-fetchflex-test-key",
                chains=chain_id,
                key=os.environ["PRIVATE_KEY"],
                password="",
            )
        else:
            raise Exception(f"Need an account for {chain_id}")

    return cfg


@pytest.fixture
def mumbai_test_cfg(scope="function", autouse=True):
    return local_node_cfg(chain_id=80001)


@pytest.fixture
def rinkeby_test_cfg(scope="function", autouse=True):
    return local_node_cfg(chain_id=4)


@pytest.fixture
def ropsten_test_cfg(scope="function", autouse=True):
    return local_node_cfg(chain_id=3)


@pytest.fixture
def goerli_test_cfg(scope="function", autouse=True):
    return local_node_cfg(chain_id=5)


@pytest.fixture(scope="function", autouse=True)
def mock_token_contract():
    """mock token to use for staking"""
    return accounts[0].deploy(
        contract=StakingToken,
        gas_price=gas_price_with_multiplier
    )


@pytest.fixture(scope="function", autouse=True)
def mock_flex_contract(mock_token_contract):
    """mock oracle(FetchFlex) contract to stake in"""
    # return accounts[0].deploy(FetchFlex, mock_token_contract.address, accounts[0], 10e18, 60)
    return accounts[0].deploy(
        FetchFlex, mock_token_contract.address, accounts[0], 10e18, 60, gas_price=gas_price_with_multiplier
    )


@pytest.fixture(scope="function", autouse=True)
def mock_autopay_contract(mock_flex_contract, mock_token_contract, query_data_storage_contract):
    """mock payments(Autopay) contract for tipping and claiming tips"""
    return accounts[0].deploy(
        Autopay,
        mock_flex_contract.address,
        mock_token_contract.address,
        query_data_storage_contract.address,
        # accounts[0],
        20,
        gas_price=gas_price_with_multiplier,
    )


@pytest.fixture(scope="function", autouse=True)
def query_data_storage_contract():
    return accounts[0].deploy(
        QueryDataStorage,
        gas_price=gas_price_with_multiplier,
    )


@pytest.fixture
def fetchx_oracle_mock_contract():
    return accounts[0].deploy(FetchXOracleMock)


@pytest.fixture
def fetchx_master_mock_contract():
    return accounts[0].deploy(FetchXMasterMock)


@pytest.fixture(autouse=True)
def multicall_contract():
    #  deploy multicall contract to brownie chain and add chain id to multicall module
    addy = brownie_multicall.deploy({"from": accounts[0], 'gas_price': gas_price_with_multiplier})
    Network.Brownie = 1337
    # add multicall contract address to multicall module
    MULTICALL2_ADDRESSES[Network.Brownie] = addy.address
    multicall.state_override_supported = lambda _: False


@pytest.fixture(scope="function")
def fetchflex_360_contract(mock_token_contract):
    account_fake = accounts.add("023861e2ceee1ea600e43cbd203e9e01ea2ed059ee3326155453a1ed3b1113a9")
    return account_fake.deploy(
        FetchFlex360,
        mock_token_contract.address,
        1,
        1,
        1,
        "0x5c13cd9c97dbb98f2429c101a2a8150e6c7a0ddaff6124ee176a3a411067ded0",
    )


@pytest_asyncio.fixture(scope="function")
async def fetch_360(mumbai_test_cfg, fetchflex_360_contract, mock_autopay_contract, mock_token_contract):
    async with TelliotCore(config=mumbai_test_cfg) as core:
        txn_kwargs = {"gas_limit": 3500000, "legacy_gas_price": 1}
        account = core.get_account()

        fetch360 = core.get_fetch360_contracts()
        fetch360.oracle.address = fetchflex_360_contract.address
        fetch360.oracle.abi = fetchflex_360_contract.abi
        fetch360.autopay.address = mock_autopay_contract.address
        fetch360.autopay.abi = mock_autopay_contract.abi
        fetch360.token.address = mock_token_contract.address

        fetch360.oracle.connect()
        fetch360.token.connect()
        fetch360.autopay.connect()

        # mint token and send to reporter address
        mock_token_contract.mint(account.address, 100000e18)

        # approve token to be spent by autopay contract
        mock_token_contract.approve(mock_autopay_contract.address, 100000e18, {"from": account.address})

        # send eth from brownie address to reporter address for txn fees
        accounts[1].transfer(account.address, "1 ether")

        # init governance address
        await fetch360.oracle.write("init", _governanceAddress=accounts[0].address, **txn_kwargs)

        return fetch360, account


@pytest_asyncio.fixture(scope="function")
async def fetch_flex_reporter(mumbai_test_cfg, mock_flex_contract, mock_autopay_contract, mock_token_contract):
    async with TelliotCore(config=mumbai_test_cfg) as core:

        account = core.get_account()

        flex = core.get_fetchflex_contracts()
        flex.oracle.address = mock_flex_contract.address
        flex.autopay.address = mock_autopay_contract.address
        flex.token.address = mock_token_contract.address

        flex.oracle.connect()
        flex.token.connect()
        flex.autopay.connect()
        flex = core.get_fetchflex_contracts()

        r = FetchFlexReporter(
            oracle=flex.oracle,
            token=flex.token,
            autopay=flex.autopay,
            endpoint=core.endpoint,
            account=account,
            chain_id=80001,
            transaction_type=0,
            min_native_token_balance=0,
        )
        # mint token and send to reporter address
        mock_token_contract.mint(account.address, 1000e18)

        # send eth from brownie address to reporter address for txn fees
        accounts[1].transfer(account.address, "1 ether")

        return r
