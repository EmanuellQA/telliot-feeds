from typing import Any
from typing import Optional
import os

import os
import click
from chained_accounts import find_accounts
from click.core import Context
from eth_typing import ChecksumAddress
from eth_utils import to_checksum_address
from telliot_core.cli.utils import async_run

from telliot_feeds.cli.utils import build_feed_from_input
from telliot_feeds.cli.utils import get_accounts_from_name
from telliot_feeds.cli.utils import parse_profit_input
from telliot_feeds.cli.utils import print_reporter_settings
from telliot_feeds.cli.utils import reporter_cli_core
from telliot_feeds.cli.utils import valid_diva_chain
from telliot_feeds.cli.utils import valid_transaction_type
from telliot_feeds.cli.utils import validate_address
from telliot_feeds.datafeed import DataFeed
from telliot_feeds.feeds import CATALOG_FEEDS
from telliot_feeds.feeds.fetch_rng_feed import assemble_rng_datafeed
from telliot_feeds.integrations.diva_protocol import DIVA_DIAMOND_ADDRESS
from telliot_feeds.integrations.diva_protocol import DIVA_FETCH_MIDDLEWARE_ADDRESS
from telliot_feeds.integrations.diva_protocol.report import DIVAProtocolReporter
from telliot_feeds.queries.query_catalog import query_catalog
from telliot_feeds.reporters.flashbot import FlashbotsReporter
from telliot_feeds.reporters.rng_interval import RNGReporter
from telliot_feeds.reporters.rng_interval_custom import RNGCustomReporter
from telliot_feeds.reporters.fetch_360 import Fetch360Reporter
from telliot_feeds.reporters.fetch_flex import FetchFlexReporter
from telliot_feeds.utils.cfg import check_endpoint
from telliot_feeds.utils.cfg import setup_config
from telliot_feeds.utils.log import get_logger
from telliot_feeds.utils.reporter_utils import create_custom_contract
from telliot_feeds.utils.reporter_utils import prompt_for_abi


logger = get_logger(__name__)


STAKE_MESSAGE = (
    "\U00002757Telliot will automatically stake more FETCH "
    "if your stake is below or falls below the stake amount required to report.\n"
    "If you would like to stake more than required, enter the TOTAL stake amount you wish to be staked.\n"
    "For example, if you wish to stake 1000 FETCH, enter 1000.\n"
)
REWARDS_CHECK_MESSAGE = (
    "If the --no-rewards-check flag is set, the reporter will not check profitability or\n"
    "available tips for the datafeed unless the user has not selected a query tag or\n"
    "used the random feeds flag.\n"
)


@click.group()
def reporter() -> None:
    """Report data on-chain."""
    pass


@click.option(
    "--account",
    "-a",
    "account_str",
    help="Name of account used for reporting, staking, etc. More info: run `telliot account --help`",
    required=True,
    nargs=1,
    type=str,
)
@click.option(
    "--signature-account",
    "-sa",
    "signature_account",
    help="Name of signature account used for reporting with Flashbots.",
    required=False,
    nargs=1,
    type=str,
)
@reporter.command()
@click.option(
    "--build-feed",
    "-b",
    "build_feed",
    help="build a datafeed from a query type and query parameters",
    is_flag=True,
)
@click.option(
    "--query-tag",
    "-qt",
    "query_tag",
    help="select datafeed using query tag",
    required=False,
    nargs=1,
    type=click.Choice([q.tag for q in query_catalog.find()]),
)
@click.option(
    "--gas-limit",
    "-gl",
    "gas_limit",
    help="use custom gas limit",
    nargs=1,
    type=int,
)
@click.option(
    "--max-fee",
    "-mf",
    "max_fee",
    help="use custom maxFeePerGas (gwei)",
    nargs=1,
    type=float,
    required=False,
)
@click.option(
    "--priority-fee",
    "-pf",
    "priority_fee",
    help="use custom maxPriorityFeePerGas (gwei)",
    nargs=1,
    type=float,
    required=False,
)
@click.option(
    "--gas-price",
    "-gp",
    "legacy_gas_price",
    help="use custom legacy gasPrice (gwei)",
    nargs=1,
    type=int,
    required=False,
)
@click.option(
    "--profit",
    "-p",
    "expected_profit",
    help="lower threshold (inclusive) for expected percent profit",
    nargs=1,
    # User can omit profitability checks by specifying "YOLO"
    type=click.UNPROCESSED,
    required=False,
    callback=parse_profit_input,
    default="100.0",
)
@click.option(
    "--tx-type",
    "-tx",
    "tx_type",
    help="choose transaction type (0 for legacy txs, 2 for EIP-1559)",
    type=click.UNPROCESSED,
    required=False,
    callback=valid_transaction_type,
    default=2,
)
@click.option(
    "-wp",
    "--wait-period",
    help="wait period between feed suggestion calls",
    nargs=1,
    type=int,
    default=7,
)
@click.option(
    "--rng-timestamp",
    "-rngts",
    "rng_timestamp",
    help="timestamp for Fetch RNG",
    nargs=1,
    type=int,
)
@click.option(
    "--diva-protocol",
    "-dpt",
    "reporting_diva_protocol",
    help="Report & settle DIVA Protocol derivative pools",
    default=False,
)
@click.option(
    "--diva-diamond-address",
    "-dda",
    "diva_diamond_address",
    help="DIVA Protocol contract address",
    nargs=1,
    type=click.UNPROCESSED,
    callback=validate_address,
    default=DIVA_DIAMOND_ADDRESS,
    prompt=False,
)
@click.option(
    "--diva-middleware-address",
    "-dma",
    "diva_middleware_address",
    help="DIVA Protocol middleware contract address",
    nargs=1,
    type=click.UNPROCESSED,
    callback=validate_address,
    default=DIVA_FETCH_MIDDLEWARE_ADDRESS,
    prompt=False,
)
@click.option(
    "--custom-token-contract",
    "-custom-token",
    "custom_token_contract",
    help="Address of custom token contract",
    nargs=1,
    default=None,
    type=click.UNPROCESSED,
    callback=validate_address,
    prompt=False,
)
@click.option(
    "--custom-oracle-contract",
    "-custom-oracle",
    "custom_oracle_contract",
    help="Address of custom oracle contract",
    nargs=1,
    default=None,
    type=click.UNPROCESSED,
    callback=validate_address,
    prompt=False,
)
@click.option(
    "--custom-autopay-contract",
    "-custom-autopay",
    "custom_autopay_contract",
    help="Address of custom autopay contract",
    nargs=1,
    default=None,
    type=click.UNPROCESSED,
    callback=validate_address,
    prompt=False,
)
@click.option(
    "--fetch-360/--fetch-flex",
    "-360/-flex",
    "fetch_360",
    default=True,
    help="Choose between Fetch 360 or Flex contracts",
)
@click.option(
    "--stake",
    "-s",
    "stake",
    help=STAKE_MESSAGE,
    nargs=1,
    type=float,
    default=100.0,
)
@click.option(
    "--min-native-token-balance",
    "-mnb",
    "min_native_token_balance",
    help="Minimum native token balance required to report. Denominated in ether.",
    nargs=1,
    type=float,
    default=0.25,
)
@click.option(
    "--check-rewards/--no-check-rewards",
    "-cr/-ncr",
    "check_rewards",
    default=True,
    help=REWARDS_CHECK_MESSAGE,
)
@click.option(
    "--random-feeds/--no-random-feeds",
    "-rf/-nrf",
    "use_random_feeds",
    default=False,
    help="Reporter will use a random datafeed from the catalog.",
)
@click.option(
    "--gas-multiplier",
    "-gm",
    "gas_multiplier",
    help="increase gas price by this percentage (default 1%) ie 5 = 5%",
    nargs=1,
    type=int,
    default=1,  # 1% above the gas price by web3
)
@click.option(
    "--use-estimate-fee/--no-use-estimate-fee",
    default=False,
)
@click.option(
    "--use-gas-api/--no-use-gas-api",
    default=False,
)
@click.option(
    "--force-nonce",
    "-fn",
    "force_nonce",
    help="Force a specific nonce when building transactions",
    nargs=1,
    type=int,
    default=None,
)
@click.option(
    "--tx-timeout",
    "-tx-timeout",
    "tx_timeout",
    help="Timeout for transaction to be mined",
    nargs=1,
    type=int,
    default=120,
)
@click.option("--rng-auto/--rng-auto-off", default=False)
@click.option("--submit-once/--submit-continuous", default=False)
@click.option("-pwd", "--password", type=str)
@click.option("-spwd", "--signature-password", type=str)
@click.option("--continue-reporting-on-dispute/--stop-reporting-on-dispute", type=bool,default=False)
@click.option(
    "--price-validation-method",
    "-pvm",
    "price_validation_method",
    help="Price validation method",
    nargs=1,
    type=str,
    default="percentage_change"
)
@click.option(
    "--price-validation-consensus",
    "-pvc",
    "price_validation_consensus",
    help="Price validation consensus",
    nargs=1,
    type=str,
    default="majority"
)
@click.option(
    "--continue-reporting-on-validator-unreachable/--stop-reporting-on-validator-unreachable",
    type=bool,
    default=False
)
@click.pass_context
@async_run
async def report(
    ctx: Context,
    query_tag: str,
    build_feed: bool,
    tx_type: int,
    gas_limit: int,
    max_fee: Optional[float],
    priority_fee: Optional[float],
    legacy_gas_price: Optional[int],
    expected_profit: str,
    submit_once: bool,
    wait_period: int,
    reporting_diva_protocol: bool,
    diva_diamond_address: Optional[str],
    diva_middleware_address: Optional[str],
    rng_timestamp: int,
    password: str,
    signature_password: str,
    rng_auto: bool,
    min_native_token_balance: float,
    custom_token_contract: Optional[ChecksumAddress],
    custom_oracle_contract: Optional[ChecksumAddress],
    custom_autopay_contract: Optional[ChecksumAddress],
    fetch_360: bool,
    stake: float,
    account_str: str,
    signature_account: str,
    check_rewards: bool,
    use_random_feeds: bool,
    gas_multiplier: int,
    use_estimate_fee: bool,
    use_gas_api: bool,
    force_nonce: Optional[int],
    tx_timeout: int,
    continue_reporting_on_dispute: bool,
    price_validation_method: str,
    price_validation_consensus: str,
    continue_reporting_on_validator_unreachable: bool,
) -> None:
    """Report values to Fetch oracle"""

    ctx.obj["ACCOUNT_NAME"] = account_str
    ctx.obj["SIGNATURE_ACCOUNT_NAME"] = signature_account

    accounts = get_accounts_from_name(account_str)
    if not accounts:
        return

    ctx.obj["CHAIN_ID"] = accounts[0].chains[0]  # used in reporter_cli_core
    # if max_fee flag is set, then priority_fee must also be set
    if (max_fee is not None and priority_fee is None) or (max_fee is None and priority_fee is not None):
        raise click.UsageError("Must specify both max fee and priority fee")
    # Initialize telliot core app using CLI context
    async with reporter_cli_core(ctx) as core:

        core._config, account = setup_config(core.config, account_name=account_str)

        endpoint = check_endpoint(core._config)

        if not endpoint or not account:
            click.echo("Accounts and/or endpoint unset.")
            click.echo(f"Account: {account}")
            click.echo(f"Endpoint: {core._config.get_endpoint()}")
            return

        # Make sure current account is unlocked
        if not account.is_unlocked:
            account.unlock(password)

        if signature_account is not None:
            sig_account = find_accounts(name=signature_account)[0]
            if not sig_account.is_unlocked:
                sig_account.unlock(signature_password)
            sig_acct_addr = to_checksum_address(sig_account.address)
        else:
            sig_acct_addr = ""

        # If we need to build a datafeed
        if build_feed:
            chosen_feed = build_feed_from_input()

            if chosen_feed is None:
                click.echo("Unable to build Datafeed from provided input")
                return

        # Use selected feed, or choose automatically
        elif query_tag is not None:
            try:
                chosen_feed: DataFeed[Any] = CATALOG_FEEDS[query_tag]  # type: ignore
            except KeyError:
                click.echo(f"No corresponding datafeed found for query tag: {query_tag}\n")
                return
        elif reporting_diva_protocol:
            if not valid_diva_chain(chain_id=core.config.main.chain_id):
                click.echo("Diva Protocol not supported for this chain")
                return
            chosen_feed = None
        elif rng_timestamp is not None:
            chosen_feed = await assemble_rng_datafeed(timestamp=rng_timestamp)
        else:
            chosen_feed = None

        print_reporter_settings(
            signature_address=sig_acct_addr,
            query_tag=query_tag,
            transaction_type=tx_type,
            gas_limit=gas_limit,
            max_fee=max_fee,
            priority_fee=priority_fee,
            legacy_gas_price=legacy_gas_price,
            expected_profit=expected_profit,
            chain_id=core.config.main.chain_id,
            reporting_diva_protocol=reporting_diva_protocol,
            stake_amount=stake,
            min_native_token_balance=min_native_token_balance,
        )

        _ = input("Press [ENTER] to confirm settings.")

        contracts = core.get_fetch360_contracts() if fetch_360 else core.get_fetchflex_contracts()

        if custom_oracle_contract:
            contracts.oracle.connect()  # set telliot_core.contract.Contract.contract attribute
            custom_oracle_abi = prompt_for_abi()
            contracts.oracle = create_custom_contract(
                original_contract=contracts.oracle,
                custom_contract_addr=custom_oracle_contract,
                custom_abi=custom_oracle_abi,
                endpoint=core.endpoint,
                account=account,
            )
            contracts.oracle.connect()

        if custom_autopay_contract:
            contracts.autopay.connect()  # set telliot_core.contract.Contract.contract attribute
            custom_autopay_abi = prompt_for_abi()
            contracts.autopay = create_custom_contract(
                original_contract=contracts.autopay,
                custom_contract_addr=custom_autopay_contract,
                custom_abi=custom_autopay_abi,
                endpoint=core.endpoint,
                account=account,
            )
            contracts.autopay.connect()

        if custom_token_contract:
            contracts.token.connect()  # set telliot_core.contract.Contract.contract attribute
            custom_token_abi = prompt_for_abi()
            contracts.token = create_custom_contract(
                original_contract=contracts.token,
                custom_contract_addr=custom_token_contract,
                custom_abi=custom_token_abi,
                endpoint=core.endpoint,
                account=account,
            )
            contracts.token.connect()

        common_reporter_kwargs = {
            "endpoint": core.endpoint,
            "account": account,
            "datafeed": chosen_feed,
            "gas_limit": gas_limit,
            "max_fee": max_fee,
            "priority_fee": priority_fee,
            "legacy_gas_price": legacy_gas_price,
            "chain_id": core.config.main.chain_id,
            "wait_period": wait_period,
            "oracle": contracts.oracle,
            "autopay": contracts.autopay,
            "token": contracts.token,
            "expected_profit": expected_profit,
            "stake": stake,
            "transaction_type": tx_type,
            "min_native_token_balance": int(min_native_token_balance * 10**18),
            "check_rewards": check_rewards,
            "use_random_feeds": use_random_feeds,
            "gas_multiplier": gas_multiplier,
        }

        if sig_acct_addr:
            reporter = FlashbotsReporter(
                signature_account=sig_account,
                **common_reporter_kwargs,
            )
        elif rng_auto:
            common_reporter_kwargs["wait_period"] = 120 if wait_period < 120 else wait_period
            reporter = RNGReporter(  # type: ignore
                **common_reporter_kwargs,
            )
        elif reporting_diva_protocol:
            diva_reporter_kwargs = {}
            if diva_diamond_address is not None:
                diva_reporter_kwargs["diva_diamond_address"] = diva_diamond_address
            if diva_middleware_address is not None:
                diva_reporter_kwargs["middleware_address"] = diva_middleware_address
            reporter = DIVAProtocolReporter(
                **common_reporter_kwargs,
                **diva_reporter_kwargs,  # type: ignore
            )
        elif fetch_360:
            reporter = Fetch360Reporter(
                **common_reporter_kwargs,
            )  # type: ignore
        else:
            if chosen_feed is not None and getattr(chosen_feed.query, 'is_custom_rng', False):
                common_reporter_kwargs["wait_period"] = int(os.getenv('REPORT_INTERVAL', "300"))
                reporter = RNGCustomReporter(**{
                    **common_reporter_kwargs,
                }) # type: ignore
            else:                
                reporter = FetchFlexReporter(**{
                    **common_reporter_kwargs,
                    "continue_reporting_on_dispute": continue_reporting_on_dispute,
                    "price_validation_method": price_validation_method,
                    "price_validation_consensus": price_validation_consensus,
                    "continue_reporting_on_validator_unreachable": continue_reporting_on_validator_unreachable,
                    "use_estimate_fee": use_estimate_fee,
                    "use_gas_api": use_gas_api,
                    "force_nonce": force_nonce,
                    "tx_timeout": tx_timeout,
                }) # type: ignore

        os.environ["PRICE_VALIDATION_METHOD"] = price_validation_method

        if submit_once:

            if chosen_feed is not None and chosen_feed.query.asset == 'validated-feed':
                await reporter.managed_feed_report(submit_once=True)
                return

            _, _ = await reporter.report_once()

        else:
            await reporter.report()
