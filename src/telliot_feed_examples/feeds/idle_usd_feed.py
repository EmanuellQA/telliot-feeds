from telliot_core.datafeed import DataFeed
from telliot_core.queries import SpotPrice
from telliot_core.sources.price.spot.coingecko import CoinGeckoSpotPriceSource
from telliot_core.sources.price.spot.nomics import NomicsSpotPriceSource
from telliot_core.sources.price_aggregator import PriceAggregator

idle_usd_median_feed = DataFeed(
    query=SpotPrice(asset="IDLE", currency="USD"),
    source=PriceAggregator(
        asset="idle",
        currency="usd",
        algorithm="median",
        sources=[
            CoinGeckoSpotPriceSource(asset="idle", currency="usd"),
            NomicsSpotPriceSource(asset="idle", currency="usd"),
        ],
    ),
)
