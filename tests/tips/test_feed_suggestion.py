import pytest
from brownie import chain
from eth_utils import to_bytes

from telliot_feeds.datafeed import DataFeed
from telliot_feeds.reporters.tips import CATALOG_QUERY_IDS
from telliot_feeds.reporters.tips.suggest_datafeed import get_feed_and_tip
from telliot_feeds.utils import log

log.DuplicateFilter.filter = lambda _, x: True


@pytest.mark.skip()
@pytest.mark.asyncio
async def test_no_tips(autopay_contract_setup, caplog):
    """Test no tips in autopay"""
    flex = await autopay_contract_setup
    await get_feed_and_tip(flex.autopay)
    assert "No one time tip funded queries available" in caplog.text
    assert "No funded feeds returned by autopay function call" in caplog.text
    assert "No tips available in autopay" in caplog.text


@pytest.mark.skip()
@pytest.mark.asyncio
async def test_funded_feeds_only(setup_datafeed, caplog):
    """Test feed tips but no one time tips and no reported timestamps"""
    flex = await setup_datafeed
    datafeed, tip = await get_feed_and_tip(flex.autopay)
    assert isinstance(datafeed, DataFeed)
    assert isinstance(tip, int)
    assert tip == int(1e18)
    assert "No one time tip funded queries available" in caplog.text


@pytest.mark.skip()
@pytest.mark.asyncio
async def test_one_time_tips_only(setup_one_time_tips, caplog):
    """Test one time tips but no feed tips"""
    flex = await setup_one_time_tips
    datafeed, tip = await get_feed_and_tip(flex.autopay)
    assert isinstance(datafeed, DataFeed)
    assert isinstance(tip, int)
    assert "No funded feeds returned by autopay function call" in caplog.text


@pytest.mark.skip()
@pytest.mark.asyncio
async def test_fetching_tips(tip_feeds_and_one_time_tips):
    """Test fetching tips when there are both feed tips and single tips
    A one time tip of 24 FETCH exists autopay and plus 1 FETCH in a feed
    its the highest so it should be the suggested query"""
    flex = await tip_feeds_and_one_time_tips
    datafeed, tip = await get_feed_and_tip(flex.autopay)
    assert isinstance(datafeed, DataFeed)
    assert isinstance(tip, int)
    # remove rng query id since it's being bypassed due to no api support
    FetchRNG_qid = "48142be0c53a531d048ba74c27bd5927b871d3f5de11a909c9e2b829c646e8fd"
    # give me length of catalog query ids - 1 if rng query id in list
    length = (
        (len(CATALOG_QUERY_IDS) - 1)
        if CATALOG_QUERY_IDS.__contains__(to_bytes(hexstr=FetchRNG_qid))
        else len(CATALOG_QUERY_IDS)
    )
    assert tip == length * int(1e18)


@pytest.mark.skip()
@pytest.mark.asyncio
async def test_fake_queryid_feed_setup(autopay_contract_setup, caplog):
    """Test feed tips but no one time tips and no reported timestamps"""
    flex = await autopay_contract_setup
    query_data = "0x00000000000000000000000000000000000000000000000000000000000000400000000000000000000000000000000000000000000000000000000000000080000000000000000000000000000000000000000000000000000000000000000953706f745072696365000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000200000000000000000000000000000000000000000000000000000000000000002"  # noqa: E501
    query_id = flex.autopay.node._web3.keccak(to_bytes(hexstr=query_data)).hex()
    # setup a feed on autopay
    _, status = await flex.autopay.write(
        "setupDataFeed",
        gas_limit=3500000,
        legacy_gas_price=1,
        _queryId=query_id,
        _reward=1,
        _startTime=chain.time(),
        _interval=21600,
        _window=60,
        _priceThreshold=1,
        _rewardIncreasePerSecond=0,
        _queryData=query_data,
        _amount=int(1 * 10**18),
    )
    assert status.ok
    datafeed, tip = await get_feed_and_tip(flex.autopay)
    assert datafeed is None
    assert tip is None
    msg = (
        "No feeds to report, all funded feeds had threshold gt zero and "
        "no API support in telliot to check if threshold is met"
    )
    assert msg in caplog.text
