# Usage

Prerequisites: [Getting Started](./getting-started.md)

To report data to Fetch oracles, or access any other functionality, use the `telliot` CLI. A basic example:

```
$ telliot report -a acct1 -ncr -qt pls-usd-spot --fetch-flex
```

**Be sure to always confirm the correct settings when prompted and read chain-specific usage sections before setting up your reporter!**

**Note that Fetch360 is not currently available in Pulsechain. Please always include --fetch-flex on the CLI for reporting to FetchFlex contract.**


# Reporting Basics

**Note: When using the `report` command, `telliot` will automatically attempt to stake the minimum required to report. To see the current stake amount, find the oracle contract on your desired chain, then call `getStakeAmount` in the contract's read functions section on the block explorer. The returned value is denominated in wei.**

## Help flag

Use the help flag to view all available commands and option flags:

```
$ telliot --help
```

The help flag shows subcommand options as well:

```
$ telliot report --help
Usage: telliot report [OPTIONS]

  Report values to Fetch oracle

Options:
  -b, --build-feed                build a datafeed from a query type and query
                                  parameters
  -qt, --query-tag [fetch-usd-spot|ohm-eth-spot|vsq-usd-spot|bct-usd-spot|dai-usd-spot|ric-usd-spot|idle-usd-spot|mkr-usd-spot|sushi-usd-spot|matic-usd-spot|usdc-usd-spot|gas-price-oracle-example|eur-usd-spot|snapshot-proposal-example|eth-usd-30day_volatility|numeric-api-response-example|diva-protocol-example|string-query-example|pls-usd-spot|eth-usd-spot|btc-usd-spot|fetch-rng-example|twap-eth-usd-example|ampleforth-uspce|ampleforth-custom|albt-usd-spot|rai-usd-spot]
                                  select datafeed using query tag
  -gl, --gas-limit INTEGER        use custom gas limit
  -mf, --max-fee INTEGER          use custom maxFeePerGas (gwei)
  -pf, --priority-fee INTEGER     use custom maxPriorityFeePerGas (gwei)
  -gp, --gas-price INTEGER        use custom legacy gasPrice (gwei)
  -p, --profit TEXT               lower threshold (inclusive) for expected
                                  percent profit
  -tx, --tx-type TEXT             choose transaction type (0 for legacy txs, 2
                                  for EIP-1559)
  -gps, --gas-price-speed [safeLow|average|fast|fastest]
                                  gas price speed for eth gas station API
  -wp, --wait-period INTEGER      wait period between feed suggestion calls
  -rngts, --rng-timestamp INTEGER
                                  timestamp for Fetch RNG
  -dpt, --diva-protocol BOOLEAN   Report & settle DIVA Protocol derivative
                                  pools
  -dda, --diva-diamond-address TEXT
                                  DIVA Protocol contract address
  -dma, --diva-middleware-address TEXT
                                  DIVA Protocol middleware contract address
  -custom-token, --custom-token-contract TEXT
                                  Address of custom token contract
  -custom-oracle, --custom-oracle-contract TEXT
                                  Address of custom oracle contract
  -custom-autopay, --custom-autopay-contract TEXT
                                  Address of custom autopay contract
  -360, --fetch-360 / -flex, --fetch-flex
                                  Choose between Fetch 360 or Flex contracts
  -s, --stake FLOAT               ❗Telliot will automatically stake more FETCH
                                  if your stake is below or falls below the
                                  stake amount required to report. If you
                                  would like to stake more than required,
                                  enter the TOTAL stake amount you wish to be
                                  staked. For example, if you wish to stake
                                  1000 FETCH, enter 1000.
  -mnb, --min-native-token-balance FLOAT
                                  Minimum native token balance required to
                                  report. Denominated in ether.
  -cr, --check-rewards / -ncr, --no-check-rewards
                                  If the --no-rewards-check flag is set, the
                                  reporter will not check profitability or
                                  available tips for the datafeed unless the
                                  user has not selected a query tag or used
                                  the random feeds flag.
  -rf, --random-feeds / -nrf, --no-random-feeds
                                  Reporter will use a random datafeed from the
                                  catalog.
  --rng-auto / --rng-auto-off
  --submit-once / --submit-continuous
  -pwd, --password TEXT
  -spwd, --signature-password TEXT
  --help 
```

### Account Flag

You must select an account (funds address) to use for reporting. To do so, use the `--account`/`-a` flags:

```
telliot --account acct1 report --fetch-flex
```

## Report Command

Use the `report` command to submit data to Fetch oracles. Example `report` command usage:

```
telliot report -a acct2 --fetch-flex
```

When calling the `report` command, `telliot` will ask you to confirm the reporter's settings:
  
```
...
Reporting query tag: pls-usd-spot
Current chain ID: 943
Expected percent profit: 100.0%
Transaction type: 0
Gas Limit: 350000
Legacy gas price (1e-18 PLS): None
Max fee (1e-18 PLS): None
Priority fee (1e-18 PLS): None
Gas price speed: fast
Desired stake amount: 10.0
Minimum native token balance: 0.25 PLS

Press [ENTER] to confirm settings.
```
The default settings are probably fine to use on testnets, but you may want to adjust them for mainnet using the `report` command flags/options.

By default, the reporter will continue to attempt reporting whenever out of reporting lock. Use the `--submit-once` flag to only report once:

```
telliot report -a staker1 --submit-once --fetch-flex
```

### Build Feed Flag

Use the build-a-feed flag (`--build-feed`) to build a DataFeed of a QueryType with one or more QueryParameters. When reporting, the CLI will list the QueryTypes this flag supports. To select a QueryType, enter a type from the list provided. Then, enter in the corresponding QueryParameters for the QueryType you have selected, and telliot will build the Query and select the appropriate source.

```
telliot report -a staker1 --build-feed --submit-once -p YOLO --fetch-flex
```

## Profit Flag

**Reporting for profit is extremely competitive and profit estimates aren't guarantees that you won't lose money!**

Use this flag (`--profit/-p`) to set an expected profit. The default is 100%, which will likely result in your reporter never attempting to report unless you're on a testnet. To bypass profitability checks, use the `"YOLO"` string:

```
telliot report -a acct1 -p YOLO --fetch-flex
```

Normal profit flag usage:

```
telliot report -a acct4 -p 2 --fetch-flex
```

**Note: Skipping profit checks does not skip checks for tips on the [AutoPay contract](https://github.com/fetchoracle/autoPay). If you'd like to skip these checks as well, use the `--no-check-rewards/-ncr` flag.**

## Gas, Fee, & Transaction Type Flags

If gas fees and transaction types (`--tx-type/-tx`) aren't specified by the user, defaults and estimates will be used/retrieved.

The `--gas-price/-gp` flag is for legacy transactions, while the `--max-fee/-mf` and `--priority-fee/-pf` flags are for type 2 transactions (EIP-1559). If sending legacy transactions, you can also override the gas price estimate speed using the `--gas-price-speed/-gps` flag. To set the gas limit used for the actual `submitValue()` transaction, use the `--gas-limit/-gl` flag.

Example usage:

```
telliot report -a acct3 -tx 0 -gl 310000 -gp 9001 -p 22 --fetch-flex
```

## Staking

If reporting to Fetch oracles, reporters can stake multiple times. The minimum value for each stake will be given by the minimum stake amount as configured in the oracle contract. You can get that information either by running `telliot report -a my-acct --fetch-flex` and a log with `STAKER INFO` showing the `Minimum stake amount` will be shown, or you can call the contract getter function `minimumStakeAmount()` directly.

The reporter will automatically attempt to stake the required amount, but if you'd like to stake more than the current minimum, use the `--stake/-s` flag.

```
telliot report -a acct1 -s 2000 -ncr -rf --fetch-flex
```

If the reporter account's actual stake is reduced after a dispute, the reporter will attempt to stake the difference in FETCH to return to the original desired stake amount.

### Withdraw Stake

To withdraw your stake, there isn't a command available. Instead, you'll have to connect your wallet to the token address on your chain's explorer, run `requestStakingWithdraw`, wait seven days, then run `withdrawStake`.

## Reporter Lock

The amount of times a reporter can submit data to a Fetch oracles is determined by the number of stakes per 12 hours.:

```
reporter_lock = 12 hours / number_of_stakes
```

So if the current min stake amount is 10 FETCH, and you have 120 FETCH staked, you can report every hour. But if the min stake abount is updated to 20 FETCH, you can only report every two hours.
