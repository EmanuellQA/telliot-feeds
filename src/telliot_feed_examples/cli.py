""" Telliot Feed Examples CLI

A simple interface for interacting with telliot example feed functionality.
"""
import asyncio
from typing import Any
from typing import Mapping
from typing import Optional
from typing import Union

import click
from click.core import Context
from telliot_core.apps.core import TelliotCore

from telliot_feed_examples.feeds import LEGACY_DATAFEEDS
from telliot_feed_examples.reporters.flashbot import FlashbotsReporter
from telliot_feed_examples.reporters.interval import IntervalReporter
from telliot_feed_examples.utils.log import get_logger

# from telliot_feed_examples.utils.oracle_write import tip_query


logger = get_logger(__name__)


def parse_profit_input(expected_profit: str) -> Optional[Union[str, float]]:
    """Parses user input expected profit and ensures
    the input is either a float or the string 'YOLO'."""
    if expected_profit == "YOLO":
        return expected_profit
    else:
        try:
            return float(expected_profit)
        except ValueError:
            click.echo("Not a valid profit input. Enter float or the string, 'YOLO'")
            return None


def print_reporter_settings(
    using_flashbots: bool,
    signature_address: str,
    legacy_id: str,
    gas_limit: int,
    priority_fee: Optional[int],
    expected_profit: str,
    chain_id: int,
    max_fee: Optional[int],
    transaction_type: int,
    legacy_gas_price: Optional[int],
    gas_price_speed: str,
) -> None:
    """Print user settings to console."""
    click.echo("")

    if using_flashbots:
        click.echo("⚡🤖⚡ Reporting through Flashbots relay ⚡🤖⚡")
        click.echo(f"Signature account: {signature_address}")

    click.echo(f"Reporting legacy ID: {legacy_id}")
    click.echo(f"Current chain ID: {chain_id}")

    if expected_profit == "YOLO":
        click.echo("🍜🍜🍜 Reporter not enforcing profit threshold! 🍜🍜🍜")
    else:
        click.echo(f"Expected percent profit: {expected_profit}%")

    click.echo(f"Transaction type: {transaction_type}")
    click.echo(f"Gas Limit: {gas_limit}")
    click.echo(f"Legacy gas price (gwei): {legacy_gas_price}")
    click.echo(f"Max fee (gwei): {max_fee}")
    click.echo(f"Priority fee (gwei): {priority_fee}")
    click.echo(f"Gas price speed: {gas_price_speed}\n")


async def get_app(obj: Mapping[str, Any]) -> TelliotCore:
    """Get an app configured using CLI context"""

    app = TelliotCore.get() or TelliotCore()

    # Replace default staker
    staker_tag = obj["STAKER_TAG"]
    if staker_tag is not None:
        stakers = app.config.stakers.find(tag=staker_tag)
        staker = stakers[0]
        default_staker = app.get_default_staker()
        default_staker.private_key = staker.private_key
        default_staker.address = staker.address
        default_staker.chain_id = staker.chain_id
        default_staker.tag = staker.tag

        app.config.main.chain_id = staker.chain_id

        # TODO: there should be a cleaner way to choose
        # the staker (some method in telliot-core)

    _ = await app.startup()

    # Ensure chain id compatible with flashbots relay
    if obj["USING_FLASHBOTS"]:
        assert app.config
        # Only supports mainnet
        assert app.config.main.chain_id == 1
        assert app.endpoint.web3.eth.chain_id == 1

    assert app.config
    assert app.tellorx

    return app


# Main CLI options
@click.group()
@click.option(
    "--staker-tag",
    "-st",
    "staker_tag",
    help="use specific staker by tag",
    required=False,
    nargs=1,
    type=str,
)
@click.option(
    "--signature-tag",
    "-sgt",
    "signature_tag",
    help="use specific signature account by tag",
    required=False,
    nargs=1,
    type=str,
    default="flashbots-sig",
)
@click.option(
    "--flashbots/--no-flashbots",
    "-fb/-nfb",
    "using_flashbots",
    type=bool,
    default=True,
)
@click.pass_context
def cli(
    ctx: Context,
    staker_tag: str,
    signature_tag: str,
    using_flashbots: bool,
) -> None:
    """Telliot command line interface"""
    ctx.ensure_object(dict)
    ctx.obj["STAKER_TAG"] = staker_tag
    ctx.obj["SIGNATURE_TAG"] = signature_tag
    ctx.obj["USING_FLASHBOTS"] = using_flashbots


# Report subcommand options
@cli.command()
@click.option(
    "--legacy-id",
    "-lid",
    "legacy_id",
    help="report to a legacy ID",
    required=True,
    nargs=1,
    type=click.Choice(["1", "2", "10", "41", "50", "59"]),
    default="1",  # ETH/USD spot price
)
@click.option(
    "--gas-limit",
    "-gl",
    "gas_limit",
    help="use custom gas limit",
    nargs=1,
    type=int,
    default=350000,
)
@click.option(
    "--max-fee",
    "-mf",
    "max_fee",
    help="use custom maxFeePerGas (gwei)",
    nargs=1,
    type=int,
    required=False,
)
@click.option(
    "--priority-fee",
    "-pf",
    "priority_fee",
    help="use custom maxPriorityFeePerGas (gwei)",
    nargs=1,
    type=int,
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
    type=str,
    default="100.0",
)
@click.option(
    "--tx-type",
    "-tx",
    "tx_type",
    help="choose transaction type (0 for legacy txs, 2 for EIP-1559)",
    type=int,
    default=0,
)
@click.option(
    "--gas-price-speed",
    "-gps",
    "gas_price_speed",
    help="gas price speed for eth gas station API",
    nargs=1,
    type=click.Choice(
        ["safeLow", "average", "fast", "fastest"],
        case_sensitive=True,
    ),
    default="fast",
)
@click.option("--submit-once/--submit-continuous", default=False)
@click.pass_context
def report(
    ctx: Context,
    legacy_id: str,
    tx_type: int,
    gas_limit: int,
    max_fee: Optional[int],
    priority_fee: Optional[int],
    legacy_gas_price: Optional[int],
    expected_profit: str,
    submit_once: bool,
    gas_price_speed: str,
) -> None:
    """Report values to Tellor oracle"""
    # Ensure valid user input for expected profit
    expected_profit = parse_profit_input(expected_profit)  # type: ignore
    if expected_profit is None:
        return

    assert tx_type in (0, 2)

    # Initialize telliot core app using CLI context
    core = asyncio.run(get_app(ctx.obj))

    using_flashbots = ctx.obj["USING_FLASHBOTS"]
    signature_tag = ctx.obj["SIGNATURE_TAG"]
    sig_staker = core.config.stakers.find(tag=signature_tag)[0]

    print_reporter_settings(
        using_flashbots=using_flashbots,
        signature_address=sig_staker.address,
        legacy_id=legacy_id,
        transaction_type=tx_type,
        gas_limit=gas_limit,
        max_fee=max_fee,
        priority_fee=priority_fee,
        legacy_gas_price=legacy_gas_price,
        expected_profit=expected_profit,
        chain_id=core.config.main.chain_id,
        gas_price_speed=gas_price_speed,
    )

    _ = input("Press [ENTER] to confirm settings.")

    chosen_feed = LEGACY_DATAFEEDS[legacy_id]

    common_reporter_kwargs = {
        "endpoint": core.endpoint,
        "private_key": core.get_default_staker().private_key,
        "master": core.tellorx.master,
        "oracle": core.tellorx.oracle,
        "datafeed": chosen_feed,
        "expected_profit": expected_profit,
        "transaction_type": tx_type,
        "gas_limit": gas_limit,
        "max_fee": max_fee,
        "priority_fee": priority_fee,
        "legacy_gas_price": legacy_gas_price,
        "gas_price_speed": gas_price_speed,
        "chain_id": core.config.main.chain_id,
    }

    if using_flashbots:
        reporter = FlashbotsReporter(
            **common_reporter_kwargs, signature_private_key=sig_staker.private_key
        )
    else:
        reporter = IntervalReporter(**common_reporter_kwargs)  # type: ignore

    if submit_once:
        _, _ = asyncio.run(reporter.report_once())
    else:
        _, _ = asyncio.run(reporter.report())


# @cli.command()
# @click.option(
#     "--legacy-id",
#     "-lid",
#     "legacy_id",
#     help="report to a legacy ID",
#     required=True,
#     nargs=1,
#     type=click.Choice(["1", "2", "10", "41", "50", "59"]),
#     default="1",  # ETH/USD spot price
# )
# @click.option(
#     "--amount-trb",
#     "-trb",
#     "amount_trb",
#     help="amount to tip in TRB for a query ID",
#     nargs=1,
#     type=float,
#     required=True,
# )
# @click.pass_context
# def tip(
#     ctx: Context,
#     legacy_id: str,
#     amount_trb: float,
# ) -> None:
#     """Tip TRB for a selected query ID"""

#     core = get_app(ctx.obj)  # Initialize telliot core app using CLI context

#     # Ensure valid legacy id
#     if legacy_id not in LEGACY_DATAFEEDS:
#         click.echo(
#             f"Invalid legacy ID. Valid choices: {', '.join(list(LEGACY_DATAFEEDS))}"
#         )
#         return

#     click.echo(f"Tipping {amount_trb} TRB for legacy ID {legacy_id}.")

#     chosen_feed = LEGACY_DATAFEEDS[legacy_id]
#     tip = int(amount_trb * 1e18)

#     tx_receipt, status = asyncio.run(
#         tip_query(
#             oracle=core.tellorx.oracle,
#             datafeed=chosen_feed,
#             tip=tip,
#         )
#     )

#     if status.ok and not status.error and tx_receipt:
#         click.echo("Success!")
#         tx_hash = tx_receipt["transactionHash"].hex()
#         # Point to relevant explorer
#         logger.info(f"View tip: \n{core.endpoint.explorer}/tx/{tx_hash}")
#     else:
#         logger.error(status)


if __name__ == "__main__":
    cli()
