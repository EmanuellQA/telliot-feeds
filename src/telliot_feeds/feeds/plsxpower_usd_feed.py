from telliot_feeds.datafeed import DataFeed
from telliot_feeds.queries.price.spot_price import SpotPrice
from telliot_feeds.sources.price.spot.pulsex_plsx_dai import PulseX_PLSXDAI_Source
from telliot_feeds.sources.price_aggregator import PriceAggregator

plsx_usd_feed = DataFeed(
    query=SpotPrice(asset="PLSX", currency="USD"),
    source=PriceAggregator(
        asset="plsx",
        currency="usd",
        algorithm="weighted_average",
        sources=[
            PulseX_PLSXDAI_Source(asset="plsx", currency="dai"),
            PulseX_PLSXDAI_Source(asset="plsx", currency="pls"),
        ],
    ),
)
