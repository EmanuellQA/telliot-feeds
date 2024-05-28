"""FetchRNG auto submitter.
submits FetchRNG values at a fixed time interval in managed feeds
"""
import calendar
import time
import os
import codecs
from typing import Any
from typing import Optional
from typing import Tuple

from eth_abi import decode_abi

from telliot_core.utils.response import error_status
from telliot_core.utils.response import ResponseStatus

from telliot_feeds.datafeed import DataFeed
from telliot_feeds.feeds.fetch_rng_custom_feed import assemble_rng_datafeed
from telliot_feeds.queries.fetch_rng_custom import FetchRNGCustom
from telliot_feeds.reporters.reporter_autopay_utils import get_feed_tip
from telliot_feeds.reporters.fetch_flex import FetchFlexReporter
from telliot_feeds.utils.log import get_logger


logger = get_logger(__name__)

INTERVAL = int(os.getenv('REPORT_INTERVAL', "300")) # 5 minutes
START_TIME = int(os.getenv('START_TIME', "1653350400")) # 2022-5-24 00:00:00 GMT
FETCH_RNG_NAME = os.getenv('FETCH_RNG_NAME', "custom") #default feed name to custom

def get_next_timestamp() -> int:
    """get next target timestamp"""
    now = calendar.timegm(time.gmtime())
    target_ts = START_TIME + (now - START_TIME) // INTERVAL * INTERVAL
    return target_ts


class RNGCustomReporter(FetchFlexReporter):
    """Reports FetchRNG values at a fixed interval to FetchFlex
    on Pulsechain."""

    async def fetch_datafeed(self) -> Optional[DataFeed[Any]]:
        status = ResponseStatus()

        rng_timestamp = get_next_timestamp()
        query = FetchRNGCustom(FETCH_RNG_NAME, START_TIME)
        timestamp_reported, read_status = await self.check_if_timestamp_reported(query.query_id, rng_timestamp)

        logger.info(f"rng_timestamp (timestamp interval): {rng_timestamp}")
        logger.info(f"Generated query id: {codecs.encode(query.query_id, 'hex')}")

        if not read_status.ok:
            status.error = "Unable to check if timestamp was reported: " + read_status.error  # error won't be none # noqa: E501
            logger.error(status.error)
            status.e = read_status.e
            return None

        if timestamp_reported:
            status.ok = False
            status.error = f"Latest timestamp in interval {rng_timestamp} already reported"
            logger.info(status.error)
            return None

        datafeed = await assemble_rng_datafeed(timestamp=rng_timestamp)
        if datafeed is None:
            msg = "Unable to assemble RNG datafeed"
            error_status(note=msg, log=logger.warning)
            return None

        logger.info(f"Datafeed: {datafeed}")

        self.datafeed = datafeed
        return datafeed


    async def ensure_profitable(self, datafeed: DataFeed[Any]) -> ResponseStatus:
        """This Reporter does not check for profitability"""
        status = ResponseStatus()
        status.ok = True
        return status


    async def check_if_timestamp_reported(self, query_id: bytes, rng_timestamp: int) -> Tuple[bool, ResponseStatus]:
        value, read_status = await self.oracle.read(func_name="getCurrentValue", _queryId=query_id)
        rng_hash, timestamp = decode_abi(["bytes32", "uint256"], value)
        return (rng_timestamp == timestamp), read_status

