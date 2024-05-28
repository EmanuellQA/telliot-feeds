"""FetchRNG auto submitter.
submits FetchRNG values at a fixed time interval
"""
import calendar
import time
import os
from typing import Any
from typing import Optional

from telliot_core.utils.response import error_status
from telliot_core.utils.response import ResponseStatus

from telliot_feeds.datafeed import DataFeed
from telliot_feeds.feeds.fetch_rng_feed import assemble_rng_datafeed
from telliot_feeds.queries.fetch_rng import FetchRNG
from telliot_feeds.reporters.reporter_autopay_utils import get_feed_tip
from telliot_feeds.reporters.fetch_flex import FetchFlexReporter
from telliot_feeds.utils.log import get_logger


logger = get_logger(__name__)

INTERVAL = os.getenv('REPORT_INTERVAL', 60 * 5) # 5 minutes
START_TIME = os.getenv('START_TIME', 1653350400) # 2022-5-24 00:00:00 GMT

def get_next_timestamp() -> int:
    """get next target timestamp"""
    now = calendar.timegm(time.gmtime())
    target_ts = START_TIME + (now - START_TIME) // INTERVAL * INTERVAL
    return target_ts


class RNGReporter(FetchFlexReporter):
    """Reports FetchRNG values at a fixed interval to FetchFlex
    on Pulsechain."""

    async def fetch_datafeed(self) -> Optional[DataFeed[Any]]:
        status = ResponseStatus()

        rng_timestamp = get_next_timestamp()
        query = FetchRNG(rng_timestamp)
        report_count, read_status = await self.get_num_reports_by_id(query.query_id)

        if not read_status.ok:
            status.error = "Unable to retrieve report count: " + read_status.error  # error won't be none # noqa: E501
            logger.error(status.error)
            status.e = read_status.e
            return None

        if report_count > 0:
            status.ok = False
            status.error = f"Latest timestamp in interval {rng_timestamp} already reported"
            logger.info(status.error)
            return None

        datafeed = await assemble_rng_datafeed(timestamp=rng_timestamp)
        if datafeed is None:
            msg = "Unable to assemble RNG datafeed"
            error_status(note=msg, log=logger.warning)
            return None
        self.datafeed = datafeed
        tip = 0

        single_tip, status = await self.autopay.get_current_tip(datafeed.query.query_id)
        if not status.ok:
            msg = "Unable to fetch single tip"
            error_status(msg, log=logger.warning)
            return None
        tip += single_tip

        feed_tip = await get_feed_tip(
            datafeed.query.query_data, self.autopay
        )  # input query data instead of query id to use tip listener
        if feed_tip is None:
            msg = "Unable to fetch feed tip"
            error_status(msg, log=logger.warning)
            return None
        tip += feed_tip
        logger.debug(f"Current tip for RNG query: {tip}")
        return datafeed