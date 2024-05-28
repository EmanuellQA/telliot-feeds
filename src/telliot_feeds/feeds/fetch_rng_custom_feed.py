"""Datafeed for pseudorandom number from hashing multiple blockhashes together."""
from typing import Optional

import os
import chained_accounts
from telliot_core.model.endpoints import RPCEndpoint

from telliot_feeds.datafeed import DataFeed
from telliot_feeds.queries.fetch_rng_custom import FetchRNGCustom
from telliot_feeds.sources.custom_blockhash_aggregator import FetchRNGCustomManualSource

FETCH_RNG_NAME = os.getenv('FETCH_RNG_NAME', "custom")
START_TIME = int(os.getenv('START_TIME', 1653350400)) # 2022-5-24 00:00:00 GMT

local_source = FetchRNGCustomManualSource()

fetch_rng_custom_feed = DataFeed(source=local_source, query=FetchRNGCustom(name=FETCH_RNG_NAME, interval=START_TIME))

async def assemble_rng_datafeed(
    timestamp: int
) -> Optional[DataFeed[float]]:
    """Assembles a FetchRNG custom datafeed for the given start timestamp."""
    local_source.set_timestamp(timestamp)
    feed = DataFeed(source=local_source, query=FetchRNGCustom(name=FETCH_RNG_NAME, interval=START_TIME))

    return feed
