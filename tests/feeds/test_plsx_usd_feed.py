import statistics

import pytest

from telliot_feeds.feeds.plsx_usd_feed import plsx_usd_feed


@pytest.mark.asyncio
async def test_plsx_usd_median_feed(caplog):
    """Retrieve weighted_average PLSX/USD price."""
    v, _ = await plsx_usd_feed.source.fetch_new_datapoint()

    assert v is not None
    assert v > 0
    assert (
        "sources used in aggregate: 1" in caplog.text.lower()
    )
    print(f"PLSX/USD Price: {v}")

    # Get list of data sources from sources dict
    source_prices = [source.latest[0] for source in plsx_usd_feed.source.sources if source.latest[0]]

    # Make sure error is less than decimal tolerance
    assert (v - statistics.median(source_prices)) < 10**-6