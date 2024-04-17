# Configuring price sources

A Telliot feed can be configured to use a specific price source. The bullet list described below presents the feeds for PLS/USD and its price sources:

* `pls-usd-spot` Feed sources
    * Pulsex Liquidity Pools Pairs
    * Coingecko
    * LiquidLoans Pulsechain Subgraph

* `pls-usd-spot-twap` Feed source
    * TWAP of a Pulsex Liquidity Pool Pair
* `pls-usd-spot-lwap` Feed source
    * LWAP on TWAP of Pulsex Liquidity Pools Pairs

A feed used by a Telliot reporter is configured with default sources. There are default configurations for SpotPrice PLS/USD Query with default PulseX Liquidity Pools (LPs) as price source, these LPs pairs are USDT/WPLS, USDC/WPLS and WPLS/DAI from Pulsechain mainnet. Below is described the default behaviour for the PLS/USD price feeds in which use these LPs as sources:

- Liquidity Weighted average price (LWAP): uses the `-qt pls-usd-spot` CLI option for a `telliot report`. It performs the liquidity average algorithm for the retrieved prices from the default Liquidity Pool pairs to return one single price.

- Time weight average price (TWAP): uses the `-qt pls-usd-spot-twap-lp` CLI option for a `telliot report`. It performs the TWAP algorithm defined as $twap = \frac{priceCumulative_2 - priceCumulative_1}{timestamp_2 - timestamp_1}$ for the default WPLS/DAI LP pair. The prices cumulative are retrieved from the LP and the default time difference for a TWAP is 30 minutes (1800 seconds).

- Liquidity weighted average price (LWAP) on Time weighted average price (TWAP): uses the `-qt pls-usd-spot-lwap` CLI option for a `telliot report`. It performs the TWAP algorithm for each default LP pair, once the prices are retrieved it calculates the liquidity average to return one single price.

It's also possible to configure Pulsex Liquidity Pools Pairs and other price sources. Using a different source will report different values.

Telliot will use the default configuration if there's no environment configuration through the `.env` file. The default config uses the Pulsex Liquidity Pools pairs which are configured with the variables `PLS_CURRENCY_SOURCES`, `PLS_ADDR_SOURCES`, `PLS_LPS_ORDER`, `TWAP_TIMESPAN` and `LP_PULSE_NETWORK_URL`. The default values for these variables are:

- `PLS_CURRENCY_SOURCES` = ["usdt", "usdc", "dai"];
- `PLS_ADDR_SOURCES` = [<br>
        "0x322Df7921F28F1146Cdf62aFdaC0D6bC0Ab80711",
        <br>
        "0x6753560538ECa67617A9Ce605178F788bE7E524E",
        <br>
        "0xE56043671df55dE5CDf8459710433C10324DE0aE"
        <br>
    ];
- `PLS_LPS_ORDER` = ["usdt/wpls", "usdc/wpls", "wpls/dai"];
- `LP_PULSE_NETWORK_URL` = https://rpc.pulsechain.com
- `TWAP_TIMESPAN` = 1800

It's important to note that the i-th value `PLS_CURRENCY_SOURCES` matches the i-th `PLS_ADDR_SOURCES` and `PLS_LPS_ORDER`. For example, for the first LP config, its currency is "usdt", with "0x322Df7921F28F1146Cdf62aFdaC0D6bC0Ab80711" LP contract address and "usdt/wpls" pair order.

When the environment variables are provided in the `.env` file, Telliot will override the default configurations to use the provided variables. The description below will show options of configuration for the LPs pairs liquidity weighted average price (LWAP) and  time weight average price (TWAP).

- Query PLS/USD options `-qt pls-usd-spot`, `-qt pls-usd-spot-twap-lp` and `-qt pls-usd-spot-lwap`.

    The SpotPrice for `pls-usd-spot` query-tag can use one of three sources: `PulsechainPulseXSource`, `CoinGeckoSpotPriceSource` or `PulsechainSubgraphSource`.

    The feed [pls_usd_feed.py](https://github.com/fetchoracle/telliot-feeds/blob/main/src/telliot_feeds/feeds/pls_usd_feed.py) uses its data sources accordingly to the environment variables in the `.env` file. The configuration process checks the existence `COINGECKO_MOCK_URL` or `PULSECHAIN_SUBGRAPH_URL` variables to determine the data source. This feed select the source as follows:

    - If the configuration variable COINGECKO_MOCK_URL is found in the .env file, the feed uses CoinGecko as the price source.
    - Alternatively, if the configuration variable PULSECHAIN_SUBGRAPH_URL is found in the .env file, the feed uses the LiquidLoans Pulsechain Subgraph URL as the source.
    - If neither of the above configuration variables is found, the feed defaults to using the `PulseX Liquidity Pools pairs`. It passes the LPs data (using the Liquidity Pool pairs config) to a Price Aggregator which uses the liquidity weighted average algorithm.

    ```sh
    # .env configuration example
    COINGECKO_MOCK_URL=https://api.coingecko.com/api/v3
    PULSECHAIN_SUBGRAPH_URL=https://subgraph-dev.liquidloans.io
    ```

    The feeds [pls_usd_twap_lp.py](https://github.com/fetchoracle/telliot-feeds/blob/main/src/telliot_feeds/feeds/pls_usd_twap_lp.py) and [pls_usd_lwap.py](https://github.com/fetchoracle/telliot-feeds/blob/main/src/telliot_feeds/feeds/pls_usd_lwap.py) uses only the source `TWAPLPSpotPriceSource` in which also uses the `PulseX Liquidity Pool pairs` configuration.
    
    To use a custom `Liquidity Pool pairs`  source configuration, the variables for `PLS_CURRENCY_SOURCES`, `PLS_ADDR_SOURCES`, `PLS_LPS_ORDER`, `LP_PULSE_NETWORK_URL` and `TWAP_TIMESPAN` must be provided, please refer the `.env.emxaple` file to see how to proper configure the `.env` file.
    
    - `PLS_CURRENCY_SOURCES`: defines the currencies that are going to be used, as "dai" for example;
    - `PLS_ADDR_SOURCES`: defines the contract addresses of the Liquidity Pools configured;
    - `PLS_LPS_ORDER`: describes the pair ordering of an LP, since the order of the token as `WPLS/DAI` and `DAI/WPLS` matters, for example;
    - `LP_PULSE_NETWORK_URL`: configures the RPC URL to Pulsechain mainnet or testnet in the `PulsechainPulseXSource` source to interact with the Liquidity Pool contract.
    - `TWAP_TIMESPAN`: configures the TWAP time elapsed to be used as $time_elapsed = timestamp_2 - timestamp_1$ in the twap calculation ($twap = \frac{priceCumulative_2 - priceCumulative_1}{timestamp_2 - timestamp_1}$). Note that this variable is only required for TWAP and LWAP feeds (pls-usd-spot-twap-lp and pls-usd-spot-lwap)

- Query FETCH/USD (`-qt fetch-usd-pot`)

    The SpotPrice for fetch-usd-spot query-tag can use one of two sources: `PulseXSupgraphSource` or `CoinGeckoSpotPriceSource`.

    The feed [fetch_usd_feed.py](https://github.com/fetchoracle/telliot-feeds/blob/dev/src/telliot_feeds/feeds/fetch_usd_feed.py) checks the environment variables in the `.env` file for its respective sources. If it finds a config for `PULSEX_SUBGRAPH_URL` it uses the PulseX Supgraph as the source, this source also requires the `FETCH_ADDRESS` environment variable. Otherwise, this feed will use the CoinGecko source (requires a configuration for `COINGECKO_MOCK_URL` variable, otherwise will use the default "https://api.coingecko.com/api/v3").

- Query PLSX/USD (`qt plsx-usd-spot`)

    The SpotPrice for plsx-usd-spot query-tag only uses `PulsechainPulseXSource` source.

    The feed [plsx_usd_feed.py](https://github.com/fetchoracle/telliot-feeds/blob/dev/src/telliot_feeds/feeds/plsx_usd_feed.py) will use the configuration for `PLSX_CURRENCY_SOURCES`, `PLSX_ADDR_SOURCES` and `PLSX_LPS_ORDER` similar to how pls-usd-spot feed is configured.

The currency sources supported for pls-usd-spot and plsx-usd-spot are "DAI", "USDC" and "USDT".
