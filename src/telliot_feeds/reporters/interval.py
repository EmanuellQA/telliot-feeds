""" BTCUSD Price Reporter
Example of a subclassed Reporter.
"""
import asyncio
import time
import threading
from typing import Any
from typing import Optional
from typing import Tuple
from typing import Union

import requests

from chained_accounts import ChainedAccount
from eth_utils import to_checksum_address
from telliot_core.contract.contract import Contract
from telliot_core.model.endpoints import RPCEndpoint
from telliot_core.utils.key_helpers import lazy_unlock_account
from telliot_core.utils.response import error_status
from telliot_core.utils.response import ResponseStatus
from web3._utils.fee_utils import _fee_history_priority_fee_estimate
from web3.contract import ContractFunction
from web3.datastructures import AttributeDict

from telliot_feeds.datafeed import DataFeed
from telliot_feeds.feeds import CATALOG_FEEDS
from telliot_feeds.feeds.eth_usd_feed import eth_usd_median_feed
from telliot_feeds.feeds.fetch_usd_feed import fetch_usd_median_feed
from telliot_feeds.feeds.managed_feeds.ManagedFeeds import managed_feeds
from telliot_feeds.utils.log import get_logger
from telliot_feeds.utils.reporter_utils import has_native_token_funds
from telliot_feeds.utils.reporter_utils import is_online
from telliot_feeds.utils.reporter_utils import fetch_suggested_report
from telliot_feeds.utils.reporter_utils import tkn_symbol
from telliot_feeds.reporters.ListenLPContract import ListenLPContract
from telliot_feeds.reporters.FlexV3 import FlexV3

logger = get_logger(__name__)


class IntervalReporter:
    """Reports values from given datafeeds to a FetchX Oracle
    every 7 seconds."""

    def __init__(
        self,
        endpoint: RPCEndpoint,
        account: ChainedAccount,
        chain_id: int,
        master: Contract,
        oracle: Contract,
        datafeed: Optional[DataFeed[Any]] = None,
        expected_profit: Union[str, float] = 100.0,
        transaction_type: int = 0,
        gas_limit: Optional[int] = None,
        max_fee: Optional[float] = None,
        priority_fee: Optional[float] = None,
        legacy_gas_price: Optional[int] = None,
        gas_multiplier: int = 1,
        wait_period: int = 10,
        min_native_token_balance: int = 10**18,
        use_estimate_fee: bool = False,
        use_gas_api: bool = False,
        force_nonce: Optional[int] = None,
        tx_timeout: int = 120,
    ) -> None:

        self.endpoint = endpoint
        self.account = account
        self.master = master
        self.oracle = oracle
        self.datafeed = datafeed
        self.chain_id = chain_id
        self.acct_addr = to_checksum_address(account.address)
        self.last_submission_timestamp = 0
        self.expected_profit = expected_profit
        self.transaction_type = transaction_type
        self.gas_limit = gas_limit
        self.max_fee = max_fee
        self.priority_fee = priority_fee
        self.legacy_gas_price = legacy_gas_price
        self.gas_multiplier = gas_multiplier
        self.fetch_usd_median_feed = fetch_usd_median_feed
        self.eth_usd_median_feed = eth_usd_median_feed
        self.wait_period = wait_period
        self.min_native_token_balance = min_native_token_balance
        self.web3 = self.endpoint._web3
        self.use_estimate_fee = use_estimate_fee
        self.use_gas_api = use_gas_api
        self.force_nonce: Optional[int] = force_nonce
        self.tx_timeout = tx_timeout

        self.gas_info: dict[str, Union[float, int]] = {}

        logger.info(f"Reporting with account: {self.acct_addr}")

    async def check_reporter_lock(self) -> ResponseStatus:
        """Ensure enough time has passed since last report
        Returns a bool signifying whether a given address is in a
        reporter lock or not (FetchX oracle users cannot submit
        multiple times within 12 hours)."""
        status = ResponseStatus()

        # Save last submission timestamp to reduce web3 calls
        if self.last_submission_timestamp == 0:
            last_timestamp, read_status = await self.oracle.read("getReporterLastTimestamp", _reporter=self.acct_addr)

            # Log web3 errors
            if (not read_status.ok) or (last_timestamp is None):
                status.ok = False
                status.error = "Unable to retrieve reporter's last report timestamp:" + read_status.error
                logger.error(status.error)
                status.e = read_status.e
                return status

            self.last_submission_timestamp = last_timestamp
            logger.info(f"Last submission timestamp: {self.last_submission_timestamp}")

        if time.time() < self.last_submission_timestamp + 43200:  # 12 hours in seconds
            status.ok = False
            status.error = "Current address is in reporter lock."
            logger.info(status.error)
            return status

        return status

    async def fetch_gas_price(self) -> Optional[float]:
        """Fetches the current gas price from an EVM network and returns
        an adjusted gas price.

        Returns:
            An optional integer representing the adjusted gas price in wei, or
            None if the gas price could not be retrieved.
        """
        try:
            price = self.web3.eth.gas_price
            priceGwei = self.web3.fromWei(price, "gwei")
        except Exception as e:
            logger.error(f"Error fetching gas price: {e}")
            return None
        # increase gas price by 1.0 + gas_multiplier
        multiplier = 1.0 + (self.gas_multiplier / 100.0)
        gas_price = (float(priceGwei) * multiplier) if priceGwei else None
        return gas_price

    async def ensure_staked(self) -> Tuple[bool, ResponseStatus]:
        """Make sure the current user is staked
        Returns a bool signifying whether the current address is
        staked. If the address is not initially, it attempts to stake with
        the address's funds."""
        status = ResponseStatus()

        gas_price_gwei = await self.fetch_gas_price()
        if not gas_price_gwei:
            note = "Unable to fetch gas price during during ensure_staked()"
            return False, error_status(note=note, log=logger.warning)

        staker_info, read_status = await self.master.read(func_name="getStakerInfo", _staker=self.acct_addr)

        if (not read_status.ok) or (staker_info is None):
            msg = "Unable to read reporters staker status: " + read_status.error  # error won't be none # noqa: E501
            status = error_status(msg, log=logger.info)
            status.e = read_status.e
            return False, status

        logger.info(f"Stake status: {staker_info[0]}")

        # Status 1: staked
        if staker_info[0] == 1:
            return True, status

        # Status 0: not yet staked
        elif staker_info[0] == 0:
            logger.info("Address not yet staked. Depositing stake.")

            _, write_status = await self.master.write(
                func_name="depositStake",
                gas_limit=350000,
                legacy_gas_price=gas_price_gwei,
            )

            if write_status.ok:
                return True, status
            else:
                msg = (
                    "Unable to stake deposit: "
                    + write_status.error
                    + f"Make sure {self.acct_addr} has enough ETH & FETCH (100)"
                )  # error won't be none # noqa: E501
                return False, error_status(msg, log=logger.info)

        # Status 3: disputed
        if staker_info[0] == 3:
            msg = "Current address disputed. Switch address to continue reporting."  # noqa: E501
            return False, error_status(msg, log=logger.info)

        # Statuses 2, 4, and 5: stake transition
        else:
            msg = "Current address is locked in dispute or for withdrawal."  # noqa: E501
            return False, error_status(msg, log=logger.info)

    async def ensure_profitable(self, datafeed: DataFeed[Any]) -> ResponseStatus:
        """Estimate profitability

        Returns a bool signifying whether submitting for a given
        queryID would generate a net profit."""
        status = ResponseStatus()

        # Get current tips and time-based reward for given queryID
        rewards, read_status = await self.oracle.read("getCurrentReward", _queryId=datafeed.query.query_id)

        # Log web3 errors
        if (not read_status.ok) or (rewards is None):
            status.ok = False
            status.error = "Unable to retrieve queryID's current rewards:" + read_status.error
            logger.error(status.error)
            status.e = read_status.e
            return status

        # Fetch token prices
        price_feeds = [self.eth_usd_median_feed, self.fetch_usd_median_feed]
        _ = await asyncio.gather(*[feed.source.fetch_new_datapoint() for feed in price_feeds])

        price_eth_usd = self.eth_usd_median_feed.source.latest[0]
        price_fetch_usd = self.fetch_usd_median_feed.source.latest[0]

        if price_eth_usd is None:
            note = "Unable to fetch ETH/USD price for profit calculation"
            return error_status(note=note, log=logger.warning)
        if price_fetch_usd is None:
            note = "Unable to fetch FETCH/USD price for profit calculation"
            return error_status(note=note, log=logger.warning)

        tips, tb_reward = rewards

        if not self.gas_info:
            return error_status("Gas info not set", log=logger.warning)

        gas_info = self.gas_info
        txn_fee = gas_info["gas_price"] * gas_info["gas_limit"]

        if gas_info["type"] == 0:
            txn_fee = gas_info["gas_price"] * gas_info["gas_limit"]
            logger.info(
                f"""

                Tips: {tips / 1e18}
                Time-based reward: {tb_reward / 1e18} FETCH
                Transaction fee: {self.web3.fromWei(txn_fee, 'gwei'):.09f} {tkn_symbol(self.chain_id)}
                Gas price: {gas_info["gas_price"]} gwei
                Gas limit: {gas_info["gas_limit"]}
                Txn type: 0 (Legacy)
                """
            )
        if gas_info["type"] == 2:
            txn_fee = gas_info["max_fee"] * gas_info["gas_limit"]
            logger.info(
                f"""

                Tips: {tips / 1e18}
                Time-based reward: {tb_reward / 1e18} FETCH
                Max transaction fee: {self.web3.fromWei(txn_fee, 'gwei')} {tkn_symbol(self.chain_id)}
                Max fee per gas: {gas_info["max_fee"]} gwei
                Max priority fee per gas: {gas_info["priority_fee"]} gwei
                Gas limit: {gas_info["gas_limit"]}
                Txn type: 2 (EIP-1559)
                """
            )

        # Calculate profit
        revenue = tb_reward + tips
        rev_usd = revenue / 1e18 * price_fetch_usd
        costs_usd = txn_fee / 1e9 * price_eth_usd
        profit_usd = rev_usd - costs_usd
        logger.info(f"Estimated profit: ${round(profit_usd, 2)}")

        percent_profit = ((profit_usd) / costs_usd) * 100
        logger.info(f"Estimated percent profit: {round(percent_profit, 2)}%")

        if (self.expected_profit != "YOLO") and (percent_profit < self.expected_profit):
            status.ok = False
            status.error = "Estimated profitability below threshold."
            logger.info(status.error)
            return status

        return status

    def get_fee_info(self) -> Tuple[Optional[float], Optional[float]]:
        """Calculate max fee and priority fee if not set
        for more info:
            https://web3py.readthedocs.io/en/v5/web3.eth.html?highlight=fee%20history#web3.eth.Eth.fee_history
        """
        if self.max_fee is None:
            try:
                fee_history = self.web3.eth.fee_history(
                    block_count=5, newest_block="latest", reward_percentiles=[25, 50, 75]
                )
                # "base fee for the next block after the newest of the returned range"
                base_fee = fee_history.baseFeePerGas[-1] / 1e9
                # estimate priority fee from fee history
                priority_fee = _fee_history_priority_fee_estimate(fee_history) / 1e9
                max_fee = base_fee + priority_fee
                return priority_fee, max_fee
            except Exception as e:
                logger.warning(f"Error in calculating gas fees: {e}")
                return None, None
        return self.priority_fee, self.max_fee

    def round_to_whole_gwei(self, wei: int) -> int:
            GWEI = 1e9
            return (wei // GWEI + int(wei % GWEI > GWEI // 2)) * GWEI
    
    def get_base_fee_multiplier(self, base_fee: int) -> int:
        GWEI = 1e9
        if base_fee <= 40 * GWEI:
            return 200
        elif base_fee <= 100 * GWEI:
            return 160
        elif base_fee <= 200 * GWEI:
            return 140
        else:
            return 120
    
    def calculate_priority_fee_estimate(self, fee_history) -> Optional[int]:
        PRIORITY_FEE_INCREASE_BOUNDARY = 200
        if not fee_history: return None

        rewards = sorted([int(r[0]) for r in fee_history.get("reward", []) if int(r[0]) > 0])

        if not rewards: return None

        percentage_increases = [
            ((next - cur) // cur) * 100 for cur, next in zip(rewards, rewards[1:])
        ]
        highest_increase = max(percentage_increases, default=0)
        highest_increase_index = percentage_increases.index(highest_increase) if highest_increase in percentage_increases else -1

        values = (
            rewards[highest_increase_index:]
            if highest_increase >= PRIORITY_FEE_INCREASE_BOUNDARY and highest_increase_index >= len(rewards) // 2
            else rewards
        )

        return values[len(values) // 2]

    def calculate_fees(self, base_fee, fee_history) -> dict[str, Union[float, int]]:
        MAX_GAS_FAST = self.web3.toWei(50000000, "gwei")
        DEFAULT_PRIORITY_FEE = self.web3.toWei(3, "gwei")
        FALLBACK_ESTIMATE = {
            "maxFeePerGas": self.web3.toWei(20, "gwei"),
            "maxPriorityFeePerGas": DEFAULT_PRIORITY_FEE,
            "baseFee": None
        }

        try:
            estimated_priority_fee = self.calculate_priority_fee_estimate(fee_history)

            max_priority_fee_per_gas = max([estimated_priority_fee or 0, DEFAULT_PRIORITY_FEE])

            multiplier = self.get_base_fee_multiplier(base_fee)

            potential_max_fee = (base_fee * multiplier) / 100
            max_fee_per_gas = (
                potential_max_fee + max_priority_fee_per_gas
                if max_priority_fee_per_gas > potential_max_fee
                else potential_max_fee
            )

            if max_fee_per_gas >= MAX_GAS_FAST or max_priority_fee_per_gas >= MAX_GAS_FAST:
                raise ValueError('Estimated gas fee was much higher than expected, erroring')

            return {
                "maxFeePerGas": self.round_to_whole_gwei(max_fee_per_gas),
                "maxPriorityFeePerGas": self.round_to_whole_gwei(max_priority_fee_per_gas),
                "baseFee": base_fee
            }
        except Exception as err:
            print(err)
            return FALLBACK_ESTIMATE

    def estimate_fees(self) -> Tuple[Optional[float], Optional[float]]:
        FEE_HISTORY_BLOCKS = 10
        FEE_HISTORY_PERCENTILE = 5
        PRIORITY_FEE_ESTIMATION_TRIGGER = self.web3.toWei(100, "gwei")

        latest_block = self.web3.eth.get_block('latest')

        base_fee = latest_block["baseFeePerGas"]

        fee_history_data = self.web3.eth.fee_history(
            block_count=FEE_HISTORY_BLOCKS, newest_block='latest', reward_percentiles=[FEE_HISTORY_PERCENTILE]
        )

        fee_history = (
            fee_history_data
            if base_fee >= PRIORITY_FEE_ESTIMATION_TRIGGER
            else None
        )
        
        return self.calculate_fees(base_fee, fee_history)

    def get_fees(self) -> Tuple[Optional[float], Optional[float]]:
        is_fees_set = self.max_fee is not None and self.priority_fee is not None

        option = None

        if is_fees_set:
            priority_fee = self.priority_fee
            max_fee = self.max_fee
            option = "--max-fee and --priority-fee"

        if not is_fees_set and self.use_estimate_fee and not self.use_gas_api:
            fees = self.estimate_fees()
            priority_fee = float(self.web3.fromWei(fees["maxPriorityFeePerGas"], "gwei"))
            max_fee = float(self.web3.fromWei(fees["maxFeePerGas"], "gwei"))
            option = "estimate_fees"
        elif not is_fees_set and self.use_gas_api and not self.use_estimate_fee:
            api_url = 'https://beacon.pulsechain.com/api/v1/execution/gasnow'
            if self.chain_id == 943:
                api_url = 'https://beacon.v4.testnet.pulsechain.com/api/v1/execution/gasnow'

            request = requests.get(url=api_url, headers={'Accept': 'application/json'})
            gas_price_gwei = self.web3.fromWei(request.json()['data']['rapid'], "gwei") 
            
            priority_fee = float(gas_price_gwei)
            max_fee = float(gas_price_gwei)
            option = "gas_api"
        elif not is_fees_set:
            priority_fee, max_fee = self.get_fee_info()
            option = "get_fee_info"

        multiplier = 1.0 + (self.gas_multiplier / 100.0)
        max_fee = max_fee * multiplier
        priority_fee = priority_fee * multiplier

        logger.info(
            f"""
            Fees Info:
            Multiplier: {self.gas_multiplier}
            Option used: "{option}"
            Priority fee after multiplier: {priority_fee}
            Max fee after multiplier: {max_fee}
            """
        )

        return priority_fee, max_fee

    async def fetch_datafeed(self) -> Optional[DataFeed[Any]]:
        if self.datafeed is None:
            suggested_qtag = await fetch_suggested_report(self.oracle)
            if suggested_qtag is None:
                logger.warning("Could not get suggested query")
                return None
            self.datafeed = CATALOG_FEEDS[suggested_qtag]  # type: ignore

        return self.datafeed

    async def get_num_reports_by_id(self, query_id: bytes) -> Tuple[int, ResponseStatus]:
        count, read_status = await self.oracle.read(func_name="getNewValueCountbyQueryId", _queryId=query_id)
        return count, read_status

    async def is_online(self) -> bool:
        return await is_online()

    def has_native_token(self) -> bool:
        """Check if account has native token funds for a network for gas fees
        of at least min_native_token_balance that is set in the cli"""
        return has_native_token_funds(self.acct_addr, self.web3, min_balance=self.min_native_token_balance)

    def get_acct_nonce(self) -> tuple[Optional[int], ResponseStatus]:
        """Get transaction count for an address"""
        try:
            return self.web3.eth.get_transaction_count(self.acct_addr), ResponseStatus()
        except ValueError as e:
            return None, error_status("Account nonce request timed out", e=e, log=logger.warning)
        except Exception as e:
            return None, error_status("Unable to retrieve account nonce", e=e, log=logger.error)

    # Estimate gas usage and set the gas limit if not provided
    def submit_val_tx_gas_limit(self, submit_val_tx: ContractFunction) -> tuple[Optional[int], ResponseStatus]:
        """Estimate gas usage for submitValue transaction
        Args:
            submit_val_tx: The submitValue transaction object
        Returns a tuple of the gas limit and a ResponseStatus object"""
        if self.gas_limit is None:
            try:
                gas_limit: int = submit_val_tx.estimateGas({"from": self.acct_addr})
                if not gas_limit:
                    return None, error_status("Unable to estimate gas for submitValue transaction")
                return gas_limit, ResponseStatus()
            except Exception as e:
                msg = "Unable to estimate gas for submitValue transaction"
                return None, error_status(msg, e=e, log=logger.error)
        return self.gas_limit, ResponseStatus()

    async def report_once(
        self,
    ) -> Tuple[Optional[AttributeDict[Any, Any]], ResponseStatus]:
        """Report query value once
        This method checks to see if a user is able to submit
        values to the FetchX oracle, given their staker status
        and last submission time. Also, this method does not
        submit values if doing so won't make a profit."""
        # Check staker status
        staked, status = await self.ensure_staked()
        if not staked or not status.ok:
            logger.warning(status.error)
            return None, status

        status = await self.check_reporter_lock()
        if not status.ok:
            return None, status

        # Get suggested datafeed if none provided
        datafeed = await self.fetch_datafeed()
        if not datafeed:
            msg = "Unable to suggest datafeed"
            return None, error_status(note=msg, log=logger.info)

        logger.info(f"Current query: {datafeed.query.descriptor}")

        # Update datafeed value
        await datafeed.source.fetch_new_datapoint()
        latest_data = datafeed.source.latest
        if latest_data[0] is None:
            msg = "Unable to retrieve updated datafeed value."
            return None, error_status(msg, log=logger.info)

        # Get query info & encode value to bytes
        query = datafeed.query
        query_id = query.query_id
        query_data = query.query_data
        try:
            value = query.value_type.encode(latest_data[0])
            logger.debug(f"IntervalReporter Encoded value: {value.hex()}")
        except Exception as e:
            msg = f"Error encoding response value {latest_data[0]}"
            return None, error_status(msg, e=e, log=logger.error)

        # Get nonce
        report_count, read_status = await self.get_num_reports_by_id(query_id)

        if not read_status.ok:
            status.error = "Unable to retrieve report count: " + read_status.error  # error won't be none # noqa: E501
            logger.error(status.error)
            status.e = read_status.e
            return None, status

        # Start transaction build
        submit_val_func = self.oracle.contract.get_function_by_name("submitValue")
        submit_val_tx = submit_val_func(
            _queryId=query_id,
            _value=value,
            _nonce=report_count,
            _queryData=query_data,
        )
        # Estimate gas usage amount
        gas_limit, status = self.submit_val_tx_gas_limit(submit_val_tx=submit_val_tx)
        if not status.ok or gas_limit is None:
            return None, status

        self.gas_info["gas_limit"] = gas_limit
        # Get account nonce
        acc_nonce, nonce_status = self.get_acct_nonce()
        if not nonce_status.ok:
            return None, nonce_status
        
        nonce = self.force_nonce if self.force_nonce is not None else acc_nonce

        # Add transaction type 2 (EIP-1559) data
        if self.transaction_type == 2:
            priority_fee, max_fee = self.get_fees()
            if priority_fee is None or max_fee is None:
                return None, error_status("Unable to suggest type 2 txn fees", log=logger.error)
            # Set gas price to max fee used for profitability check
            self.gas_info["type"] = 2
            self.gas_info["max_fee"] = max_fee
            self.gas_info["priority_fee"] = priority_fee
            self.gas_info["base_fee"] = max_fee - priority_fee

            built_submit_val_tx = submit_val_tx.buildTransaction(
                {
                    "nonce": nonce,
                    "gas": gas_limit,
                    "maxFeePerGas": self.web3.toWei(max_fee, "gwei"),
                    # TODO: Investigate more why etherscan txs using Flashbots have
                    # the same maxFeePerGas and maxPriorityFeePerGas. Example:
                    # https://etherscan.io/tx/0x0bd2c8b986be4f183c0a2667ef48ab1d8863c59510f3226ef056e46658541288 # noqa: E501
                    "maxPriorityFeePerGas": self.web3.toWei(priority_fee, "gwei"),  # noqa: E501
                    "chainId": self.chain_id,
                }
            )
        # Add transaction type 0 (legacy) data
        else:
            # Fetch legacy gas price if not provided by user
            if not self.legacy_gas_price:
                gas_price = await self.fetch_gas_price()
                if not gas_price:
                    note = "Unable to fetch gas price for tx type 0"
                    return None, error_status(note, log=logger.warning)

            else:
                gas_price = self.legacy_gas_price
            # Set gas price to legacy gas price used for profitability check
            self.gas_info["type"] = 0
            self.gas_info["gas_price"] = gas_price
            built_submit_val_tx = submit_val_tx.buildTransaction(
                {
                    "nonce": nonce,
                    "gas": gas_limit,
                    "gasPrice": self.web3.toWei(gas_price, "gwei"),
                    "chainId": self.chain_id,
                }
            )

        # Check if profitable if not YOLO
        status = await self.ensure_profitable(datafeed)
        if not status.ok:
            return None, status

        lazy_unlock_account(self.account)
        local_account = self.account.local_account
        tx_signed = local_account.sign_transaction(built_submit_val_tx)

        # Ensure reporter lock is checked again after attempting to submit val
        self.last_submission_timestamp = 0

        try:
            logger.debug("Sending submitValue transaction")
            tx_hash = self.web3.eth.send_raw_transaction(tx_signed.rawTransaction)
        except Exception as e:
            note = "Send transaction failed"
            return None, error_status(note, log=logger.error, e=e)

        try:
            # Confirm transaction
            tx_receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=self.tx_timeout)

            tx_url = f"{self.endpoint.explorer}/tx/{tx_hash.hex()}"

            if tx_receipt["status"] == 0:
                msg = f"Transaction reverted. ({tx_url})"
                return tx_receipt, error_status(msg, log=logger.error)

        except Exception as e:
            note = "Failed to confirm transaction"
            return None, error_status(note, log=logger.error, e=e)

        if status.ok and not status.error:
            logger.info(f"View reported data: \n{tx_url}")
        else:
            logger.error(status)

        return tx_receipt, status
    
    async def managed_feed_report(self, submit_once: bool = False) -> None:
        logger.info("Using managed feed to submit values")

        datafeed = await self.fetch_datafeed()

        current_report_time = { "timestamp": time.time() }
        sync_event = threading.Event()
        time_limit_event = threading.Event()
        is_submitting_report = threading.Event()

        flexV3 = FlexV3(
                datafeed=datafeed,
                endpoint=self.endpoint,
                account=self.account,
                chain_id=self.chain_id,
                get_fees=self.get_fees,
                oracle=self.oracle,
                price_validation_method=self.price_validation_method,
                price_validation_consensus=self.price_validation_consensus,
                continue_reporting_on_validator_unreachable=self.continue_reporting_on_validator_unreachable)
        listen_lp_contract = ListenLPContract(
            sync_event=sync_event,
            time_limit_event=time_limit_event,
            is_submitting_report=is_submitting_report,
            current_report_time=current_report_time,
            fetch_new_datapoint=flexV3.fetch_new_datapoint
        )
        await listen_lp_contract.initialize_price()

        listen_lp_contract.listen_sync_events()

        sync_event.set()
        logger.info("Triggered first LP sync event report")
        while True:
            self.handle_rpc_connection_failures()

            logger.info("Waiting for LP sync event report trigger...")
            sync_event.wait()
            
            if time_limit_event.is_set():
                logger.info("Time limit reached! Submitting price")

            logger.info("Report triggered")
            is_submitting_report.set()
            await flexV3.callSubmitValue()
            current_report_time["timestamp"] = time.time()
            sync_event.clear()
            time_limit_event.clear()
            is_submitting_report.clear()

            if submit_once: break

    def handle_rpc_connection_failures(self) -> None:
        rpc_connection_failures = 0
        rpc_connection_failures_limit = 5

        while rpc_connection_failures < rpc_connection_failures_limit:
            if self.web3.isConnected(): return

            rpc_connection_failures += 1
            logger.warning(f"{self.web3.provider} failure {rpc_connection_failures}/{rpc_connection_failures_limit}")
            if rpc_connection_failures == rpc_connection_failures_limit:
                logger.error(f"{self.web3.provider} not connected, exiting")
                raise SystemExit(1)

    async def report(self, report_count: Optional[int] = None) -> None:
        """Submit values to Fetch oracles on an interval."""

        datafeed = await self.fetch_datafeed()

        try:
            asset = getattr(datafeed.query, 'asset', '')
        except:
            asset = ''
            logger.warning("Could not fetch datafeed")

        if asset in managed_feeds.assets:
            await self.managed_feed_report()
        else:
            while report_count is None or report_count > 0:
                self.handle_rpc_connection_failures()
                    
                online = await self.is_online()
                if online:
                    if self.has_native_token():
                        _, _ = await self.report_once()
                else:
                    logger.warning("Unable to connect to the internet!")

                logger.info(f"Sleeping for {self.wait_period} seconds")
                await asyncio.sleep(self.wait_period)

                if report_count is not None:
                    report_count -= 1
