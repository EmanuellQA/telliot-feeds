from telliot_feeds.datafeed import DataFeed
from telliot_feeds.queries.price.spot_price import SpotPrice
from telliot_feeds.sources.price.spot.twap_lp import TWAPLPSpotPriceSource
from dotenv import load_dotenv
from telliot_feeds.utils.log import get_logger
import os

load_dotenv()
logger = get_logger(__name__)

DEFAULT_LP_CURRENCY = 'dai'

def get_currency():
    if not os.getenv("PLS_CURRENCY_SOURCES"):
        logger.info(f"Using default '{DEFAULT_LP_CURRENCY}' as currency for PLS TWAP LP feed")
        return DEFAULT_LP_CURRENCY
    currency_sources = os.getenv("PLS_CURRENCY_SOURCES").split(',')
    if len(currency_sources) > 1: logger.info(f"Using {currency_sources[0]} as currency for PLS TWAP LP feed")
    return currency_sources[0]

pls_usd_twap_lp_feed = DataFeed(
    query=SpotPrice(
        asset="pls",
        currency="usd"
     ),
    source=TWAPLPSpotPriceSource(
        asset="pls",
        currency=get_currency()
    )
)