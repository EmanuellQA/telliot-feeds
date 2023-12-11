# Configuring price sources

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

When the environment variables are provided in the `.env` file, Telliot will override the default configurations to use the provided variables. The description below will show options of configuration for the LPs pairs weighted average, time weight average price (TWAP) and volume weighted average price (VWAP).

- Query PLS/USD options `-qt pls-usd-spot`, `-qt pls-usd-spot-twap-lp` and `-qt pls-usd-spot-vwap`.

    The SpotPrice for `pls-usd-spot` query-tag can use one of three sources: `PulsechainPulseXSource`, `CoinGeckoSpotPriceSource` or `PulsechainSubgraphSource`.

    The feed [pls_usd_feed.py](https://github.com/fetchoracle/telliot-feeds/blob/main/src/telliot_feeds/feeds/pls_usd_feed.py) uses its data sources accordingly to the environment variables in the `.env` file. The configuration process checks the `COINGECKO_MOCK_URL` and `PULSECHAIN_SUBGRAPH_URL` variables to determine the data source.

    ```sh
    COINGECKO_MOCK_URL=https://api.coingecko.com/api/v3
    PULSECHAIN_SUBGRAPH_URL=https://subgraph-dev.liquidloans.io
    ```

    When a configuration variable for `COINGECKO_MOCK_URL` is found in the `.env`, it uses CoinGecko as the source. Alternatively, it checks for `PULSECHAIN_SUBGRAPH_URL` to use a LiquidLoans Pulsechain Subgraph URL. If neither configuration is found, the feed uses the default `PulseX Liquidity Pools pairs` in which passes its data to a Price Aggregator with the weighted average algorithm, using the Liquidity Pool pairs configuration.

    The feeds [pls_usd_twap_lp.py](https://github.com/fetchoracle/telliot-feeds/blob/main/src/telliot_feeds/feeds/pls_usd_twap_lp.py) and [pls_usd_vwap.py](https://github.com/fetchoracle/telliot-feeds/blob/main/src/telliot_feeds/feeds/pls_usd_vwap.py) uses only the source `TWAPLPSpotPriceSource` in which also uses the `PulseX Liquidity Pool pairs` configuration.
    
    To use a custom configuration for the `Pulsex Liquidity Pool pairs` source, variables for `PLS_CURRENCY_SOURCES`, `PLS_ADDR_SOURCES`, `PLS_LPS_ORDER`, `LP_PULSE_NETWORK_URL` and `TWAP_TIMESPAN` must be provided, please refer the `.env.emxaple` file to see how to proper configure the `.env` file.
    
    - `PLS_CURRENCY_SOURCES`: defines the currencies that are going to be used, as "dai" for example;
    - `PLS_ADDR_SOURCES`: defines the contract addresses of the Liquidity Pools configured;
    - `PLS_LPS_ORDER`: describes the pair ordering of an LP, since the order of the token as `WPLS/DAI` and `DAI/WPLS` matters, for example;
    - `LP_PULSE_NETWORK_URL`: configures the RPC URL to Pulsechain mainnet or testnet in the `PulsechainPulseXSource` source to interact with the Liquidity Pool contract.
    - `TWAP_TIMESPAN`: configures the TWAP time elapsed to be used as $time_elapsed = timestamp_2 - timestamp_1$ in the twap calculation ($twap = \frac{priceCumulative_2 - priceCumulative_1}{timestamp_2 - timestamp_1}$). Note that this variable is only required for TWAP and VWAP feeds (pls-usd-spot-twap-lp and pls-usd-spot-vwap)

- Query FETCH/USD (`-qt fetch-usd-pot`)

    The SpotPrice for fetch-usd-spot query-tag can use one of two sources: `PulseXSupgraphSource` or `CoinGeckoSpotPriceSource`.

    The feed [fetch_usd_feed.py](https://github.com/fetchoracle/telliot-feeds/blob/dev/src/telliot_feeds/feeds/fetch_usd_feed.py) checks the environment variables in the `.env` file for its respective sources. If it finds a config for `PULSEX_SUBGRAPH_URL` it uses the PulseX Supgraph as the source, this source also requires the `FETCH_ADDRESS` environment variable. Otherwise, this feed will use the CoinGecko source (requires a configuration for `COINGECKO_MOCK_URL` variable, otherwise will use the default "https://api.coingecko.com/api/v3").

- Query PLSX/USD (`qt plsx-usd-spot`)

    The SpotPrice for plsx-usd-spot query-tag only uses `PulsechainPulseXSource` source.

    The feed [plsx_usd_feed.py](https://github.com/fetchoracle/telliot-feeds/blob/dev/src/telliot_feeds/feeds/plsx_usd_feed.py) will use the configuration for `PLSX_CURRENCY_SOURCES`, `PLSX_ADDR_SOURCES` and `PLSX_LPS_ORDER` similar to how pls-usd-spot feed is configured.

The currency sources supported for pls-usd-spot and plsx-usd-spot are "DAI", "USDC" and "USDT".
