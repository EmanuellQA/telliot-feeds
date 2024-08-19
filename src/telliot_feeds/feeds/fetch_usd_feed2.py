"""Datafeed for current price of FETCH in USD."""
from telliot_feeds.datafeed import DataFeed
from telliot_feeds.queries.price.spot_price import SpotPrice
from telliot_feeds.sources.price.spot.coingecko2 import CoinGeckoSpotPriceSource2
from telliot_feeds.sources.price.spot.pulsex_subgraph import PulseXSupgraphSource
from dotenv import load_dotenv
import os

load_dotenv()

if os.getenv("PULSEX_SUBGRAPH_URL") and os.getenv("FETCH_ADDRESS"):
    fetch_usd_median_feed2 = DataFeed(
        query=SpotPrice(asset="fetch", currency="usd"),
        source=PulseXSupgraphSource(asset="fetch", currency="usd")
    )
else:
    fetch_usd_median_feed2 = DataFeed(
        query=SpotPrice(asset="fetch", currency="usd"),
        source=CoinGeckoSpotPriceSource2(asset="fetch", currency="usd")
    )