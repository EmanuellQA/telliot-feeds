from unittest import mock

import pytest

from telliot_feeds.feeds.eth_usd_feed import eth_usd_median_feed
from telliot_feeds.feeds.snapshot_feed import snapshot_manual_feed
from telliot_feeds.reporters.rewards.time_based_rewards import get_time_based_rewards
from telliot_feeds.reporters.fetch_360 import Fetch360Reporter


txn_kwargs = {"gas_limit": 3500000, "legacy_gas_price": 1}
CHAIN_ID = 80001


@pytest.mark.skip("Fetch360 not available for Pulsechain")
@pytest.mark.asyncio
async def test_report(fetch_360, caplog, guaranteed_price_source):
    """Test 360 reporter deposit and balance changes when stakeAmount changes"""
    contracts, account = fetch_360
    feed = eth_usd_median_feed
    feed.source = guaranteed_price_source

    r = Fetch360Reporter(
        oracle=contracts.oracle,
        token=contracts.token,
        autopay=contracts.autopay,
        endpoint=contracts.oracle.node,
        account=account,
        chain_id=CHAIN_ID,
        transaction_type=0,
        min_native_token_balance=0,
        datafeed=feed,
        check_rewards=False,
    )

    await r.report_once()
    assert r.staker_info.stake_balance == int(1e18)
    # report count before first submission
    assert r.staker_info.reports_count == 0

    # update stakeamount increase causes reporter to deposit more to keep reporting
    await r.oracle.write("updateStakeAmount", _amount=int(20e18), **txn_kwargs)
    stake_amount, status = await r.oracle.read("getStakeAmount")
    assert status.ok
    assert stake_amount == int(20e18)

    await r.report_once()
    # staker balance increased due to updateStakeAmount call
    assert r.staker_info.stake_balance == stake_amount
    assert "Currently in reporter lock. Time left: 11:59" in caplog.text  # 12hr
    # report count before second report
    assert r.staker_info.reports_count == 1
    # decrease stakeAmount should increase reporting frequency
    await r.oracle.write("updateStakeAmount", _amount=int(10e18), **txn_kwargs)
    stake_amount, status = await r.oracle.read("getStakeAmount")
    assert status.ok
    assert stake_amount == int(10e18)

    assert r.staker_info.stake_balance == int(20e18)

    await r.report_once()
    assert "Currently in reporter lock. Time left: 5:59" in caplog.text  # 6hr

@pytest.mark.skip("Fetch360 not available for Pulsechain")
@pytest.mark.asyncio
async def test_fail_get_account_nonce(fetch_360, caplog, guaranteed_price_source, monkeypatch):
    """Test 360 reporter fails to retrieve account nonce"""
    contracts, account = fetch_360
    feed = eth_usd_median_feed
    feed.source = guaranteed_price_source

    r = Fetch360Reporter(
        oracle=contracts.oracle,
        token=contracts.token,
        autopay=contracts.autopay,
        endpoint=contracts.oracle.node,
        account=account,
        chain_id=CHAIN_ID,
        transaction_type=0,
        min_native_token_balance=0,
        datafeed=feed,
    )

    def mock_raise(*args, **kwargs):
        raise ValueError()

    with mock.patch("web3.eth.Eth.get_transaction_count", side_effect=mock_raise):
        val, status = r.get_acct_nonce()
        assert not status.ok
        assert val is None
        assert "Account nonce request timed out" in caplog.text

    class UnknownException(Exception):
        pass

    def mock_raise_unknown(*args, **kwargs):
        raise UnknownException()

    with mock.patch("web3.eth.Eth.get_transaction_count", side_effect=mock_raise_unknown):
        val, status = r.get_acct_nonce()
        assert not status.ok
        assert val is None
        assert "Unable to retrieve account nonce: UnknownException" in caplog.text


@pytest.mark.skip("Fetch360 not available for Pulsechain")
@pytest.mark.asyncio
async def test_get_time_based_rewards(fetch_360, caplog):

    contracts, _ = fetch_360
    tbr = await get_time_based_rewards(contracts.oracle)

    assert tbr >= 0
    assert isinstance(tbr, int)
    assert "not found in contract abi" not in caplog.text


@pytest.mark.skip("Fetch360 not available for Pulsechain")
@pytest.mark.asyncio
async def test_360_reporter_rewards(fetch_360, guaranteed_price_source):

    contracts, account = fetch_360
    feed = eth_usd_median_feed
    feed.source = guaranteed_price_source

    r = Fetch360Reporter(
        oracle=contracts.oracle,
        token=contracts.token,
        autopay=contracts.autopay,
        endpoint=contracts.oracle.node,
        account=account,
        chain_id=CHAIN_ID,
        transaction_type=0,
        min_native_token_balance=0,
        datafeed=feed,
    )

    assert isinstance(await r.rewards(), int)


@pytest.mark.skip("Fetch360 not available for Pulsechain")
@pytest.mark.asyncio
async def test_adding_stake(fetch_360, guaranteed_price_source):
    """Test 360 reporter depositing more stake"""
    contracts, account = fetch_360
    feed = eth_usd_median_feed
    feed.source = guaranteed_price_source

    reporter_kwargs = {
        "oracle": contracts.oracle,
        "token": contracts.token,
        "autopay": contracts.autopay,
        "endpoint": contracts.oracle.node,
        "account": account,
        "chain_id": CHAIN_ID,
        "transaction_type": 0,
        "min_native_token_balance": 0,
        "datafeed": feed,
    }
    reporter = Fetch360Reporter(**reporter_kwargs)

    # check stake amount
    stake_amount, status = await reporter.oracle.read("getStakeAmount")
    assert status.ok
    assert stake_amount == int(1e18), "Should be 1e18"

    # check default stake value
    assert reporter.stake == 0

    # first should deposits default stake
    _, status = await reporter.report_once()
    assert status.ok
    assert reporter.staker_info.stake_balance == int(1e18), "Staker balance should be 1e18"

    # stake more by by changing stake from default similar to how a stake amount chosen in cli
    # high stake to bypass reporter lock
    reporter = Fetch360Reporter(**reporter_kwargs, stake=90000)
    _, status = await reporter.report_once()
    assert status.ok
    assert reporter.staker_info.stake_balance == pytest.approx(90000e18), "Staker balance should be 90000e18"


@pytest.mark.skip("Fetch360 not available for Pulsechain")
@pytest.mark.asyncio
async def test_no_native_token(fetch_360, caplog, guaranteed_price_source):
    """Test reporter quits if no native token"""
    contracts, account = fetch_360
    feed = eth_usd_median_feed
    feed.source = guaranteed_price_source

    reporter_kwargs = {
        "oracle": contracts.oracle,
        "token": contracts.token,
        "autopay": contracts.autopay,
        "endpoint": contracts.oracle.node,
        "account": account,
        "chain_id": CHAIN_ID,
        "transaction_type": 0,
        "wait_period": 0,
        "min_native_token_balance": 100 * 10**18,
        "datafeed": feed,
    }
    reporter = Fetch360Reporter(**reporter_kwargs)

    await reporter.report(report_count=1)

    assert "insufficient native token funds" in caplog.text.lower()


@pytest.mark.skip("Fetch360 not available for Pulsechain")
@pytest.mark.asyncio
async def test_checks_reporter_lock_when_manual_source(fetch_360, monkeypatch, caplog, guaranteed_price_source):
    """Test reporter lock check when reporting for a tip that requires a manaul data source"""
    contracts, account = fetch_360
    feed = eth_usd_median_feed
    feed.source = guaranteed_price_source

    reporter_kwargs = {
        "oracle": contracts.oracle,
        "token": contracts.token,
        "autopay": contracts.autopay,
        "endpoint": contracts.oracle.node,
        "account": account,
        "chain_id": CHAIN_ID,
        "transaction_type": 0,
        "wait_period": 0,
        "min_native_token_balance": 0,
        "datafeed": feed,
    }

    # mock get_feed_and_tip, which is called in the Fetch360Reporter.fetch_datafeed method
    async def mock_get_feed_and_tip(*args, **kwargs):
        return [snapshot_manual_feed, int(1e18)]

    monkeypatch.setattr("telliot_feeds.reporters.fetch_360.get_feed_and_tip", mock_get_feed_and_tip)
    reporter = Fetch360Reporter(**reporter_kwargs)

    # report once to trigger reporter lock next time
    reporter.datafeed = eth_usd_median_feed
    _, status = await reporter.report_once()
    assert status.ok

    # set datafeed to None so fetch_datafeed will call get_feed_and_tip
    reporter.datafeed = None
    await reporter.report(report_count=1)
    assert "Currently in reporter lock. Time left: 11:59" in caplog.text


@pytest.mark.skip("Fetch360 not available for Pulsechain")
@pytest.mark.asyncio
async def test_fail_gen_query_id(fetch_360, monkeypatch, caplog, guaranteed_price_source):
    """Test failure to generate query id when calling rewards() method."""
    contracts, account = fetch_360
    feed = eth_usd_median_feed
    feed.source = guaranteed_price_source

    reporter_kwargs = {
        "oracle": contracts.oracle,
        "token": contracts.token,
        "autopay": contracts.autopay,
        "endpoint": contracts.oracle.node,
        "account": account,
        "chain_id": CHAIN_ID,
        "transaction_type": 0,
        "wait_period": 0,
        "min_native_token_balance": 0,
        "datafeed": feed,
    }

    # This will cause the SpotPrice query to throw an eth_abi.exceptions.EncodingTypeError when
    # trying to generate the query data for the query id.
    eth_usd_median_feed.query.asset = None

    reporter = Fetch360Reporter(**reporter_kwargs)
    _ = await reporter.rewards()

    assert "Unable to generate data/id for query" in caplog.text
