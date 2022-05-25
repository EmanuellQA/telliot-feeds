from telliot_core.datafeed import DataFeed
from telliot_core.queries import SpotPrice
from telliot_core.sources.price.spot.binance import BinanceSpotPriceSource
from telliot_core.sources.price.spot.bittrex import BittrexSpotPriceSource
from telliot_core.sources.price.spot.coinbase import CoinbaseSpotPriceSource
from telliot_core.sources.price.spot.coingecko import CoinGeckoSpotPriceSource
from telliot_core.sources.price.spot.gemini import GeminiSpotPriceSource
from telliot_core.sources.price.spot.kraken import KrakenSpotPriceSource
from telliot_core.sources.price_aggregator import PriceAggregator

mkr_usd_median_feed = DataFeed(
    query=SpotPrice(asset="MKR", currency="USD"),
    source=PriceAggregator(
        asset="mkr",
        currency="usd",
        algorithm="median",
        sources=[
            CoinGeckoSpotPriceSource(asset="mkr", currency="usd"),
            BittrexSpotPriceSource(asset="mkr", currency="usdt"),
            BinanceSpotPriceSource(asset="mkr", currency="usdt"),
            CoinbaseSpotPriceSource(asset="mkr", currency="usd"),
            GeminiSpotPriceSource(asset="mkr", currency="usd"),
            KrakenSpotPriceSource(asset="mkr", currency="usd"),
        ],
    ),
)
