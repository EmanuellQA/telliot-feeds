"""Datafeed for pseudorandom number from hashing multiple blockhashes together."""
from typing import Optional

import chained_accounts
from telliot_core.model.endpoints import RPCEndpoint

from telliot_feeds.datafeed import DataFeed
from telliot_feeds.queries.fetch_rng import FetchRNG
from telliot_feeds.sources.blockhash_aggregator import FetchRNGManualSource

local_source = FetchRNGManualSource()

fetch_rng_feed = DataFeed(source=local_source, query=FetchRNG(timestamp=local_source.timestamp))


async def assemble_rng_datafeed(
    timestamp: int
) -> Optional[DataFeed[float]]:
    """Assembles a FetchRNG datafeed for the given timestamp."""
    local_source.set_timestamp(timestamp)
    feed = DataFeed(source=local_source, query=FetchRNG(timestamp=timestamp))

    return feed
