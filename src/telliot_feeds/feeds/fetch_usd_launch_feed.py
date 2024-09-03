"""Datafeed for launch price of FETCH in USD."""
from telliot_feeds.datafeed import DataFeed
from telliot_feeds.queries.price.spot_price import SpotPrice
from telliot_feeds.sources.price.spot.launch_price import LaunchpriceSource
from dotenv import load_dotenv

load_dotenv()

fetch_usd_launch_feed = fetch_usd_median_feed2 = DataFeed(
    query=SpotPrice(asset="fetch", currency="usd"),
    source=LaunchpriceSource(asset="fetch", currency="usd")
)
    