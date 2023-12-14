# Fees estimation

There are 4 options for calculating the `maxFeePerGas` and `maxPriorityFeePerGas` fees of EIP-1559 transactions: Arbitral values, Gas API, Pulsechain gas estimator and current state with a multiplier.

**The default value for the --gas-multiplier (or -gm) flag is 1%, which means the fees will be multiplied by 1.01 (1% above). To not multiply the fees by any value set -gm 0**

**For all of the 4 options, the maxFeePerGas and maxPriorityFeePerGas calculated will be multiplied by the value of --gas-multiplier**

## Arbitral values

Manually set arbitral values with the --max-fee and --priority-fee telliot flags, for `maxFeePerGas` and `maxPriorityFeePerGas`, respectively. **The values should be in GWEI format, for example, if you want to use 1500000000 WEI as maxPriorityFeePerGas you need to pass -mf 1.5 GWEI**

Usage example:

```sh
telliot report -a <account-name> -qt pls-usd-spot -s 150000000 -ncr --fetch-flex --submit-once -mf 20000 -pf 1.5 -gm 10
```

That report will use `maxFeePerGas` as 20000 GWEI and `maxPriorityFeePerGas` as 1.5 GWEI, and will also increase these values by 10%.

Expected log result example:
```sh
INFO    | telliot_feeds.reporters.interval | 
            Fees Info:
            Multiplier: 10
            Option used: "--max-fee and --priority-fee"
            Priority fee after multiplier: 1.6500000000000001
            Max fee after multiplier: 22000.0
```

## Current state 

Calculate the fees in accordance with the current state of the [fetchoracle/telliot-feeds branch dev](https://github.com/fetchoracle/telliot-feeds/blob/dev/src/telliot_feeds/reporters/interval.py#L275) but this time also multiplying these values by --gas-multiplier

Usage example:

```sh
telliot report -a <account-name> -qt pls-usd-spot -s 150000000 -ncr --fetch-flex --submit-once -gm 20
```

It will use the current calculation used by fetchoracle/telliot-feeds, called `get_fee_info` to retrieve the fees. It will also increase the retrieved values by 20%.

Expected log result example:
```sh
INFO    | telliot_feeds.reporters.interval | 
            Fees Info:
            Multiplier: 20
            Option used: "get_fee_info"
            Priority fee after multiplier: 1.7999999999999998
            Max fee after multiplier: 2261.4017071452
```

## Gas Price API

It will set the values for `maxFeePerGas` and `maxPriorityFeePerGas` equals to the "Rapid" price of the [Pulsechain mainnet Gas API](https://beacon.pulsechain.com/api/v1/execution/gasnow) or [Pulsechain testnet Gas API](https://beacon.v4.testnet.pulsechain.com/api/v1/execution/gasnow) if using telliot in pulsev4 testnet.

Usage example:
```sh
telliot report -a <account-name> -qt pls-usd-spot -s 150000000 -ncr --fetch-flex --submit-once --use-gas-api
```

It will use Pulsechain gas API "Rapid" price as fees, note that the multiplier is 1, which is the default since this example did not pass any value for `-gm`.

Expected log result example:
```sh
INFO    | telliot_feeds.reporters.interval | 
            Fees Info:
            Multiplier: 1
            Option used: "gas_api"
            Priority fee after multiplier: 226027.9
            Max fee after multiplier: 226027.9
```

## Fees Estimation

Estimate the fees using the EIP-1559 Gas Estimation calculations provided by the [Pulsechain Gas Estimation repository](https://gitlab.com/pulsechaincom/gas-estimation).

Usage example:
```sh
telliot report -a <account-name> -qt pls-usd-spot -s 150000000 -ncr --fetch-flex --submit-once --use-estimate-fee
```

That report will use the same EIP-1559 Calculations in the (eip1559.ts)[https://gitlab.com/pulsechaincom/gas-estimation/-/blob/master/src/eip1559.ts?ref_type=heads] provided by the Pulsechain. Note, that the Gitlab repository was found in the footer of the Pulsechain Gas API, please see https://beacon.pulsechain.com/gasnow.

Expected log result example:
```sh
INFO    | telliot_feeds.reporters.interval | 
            Fees Info:
            Multiplier: 1
            Option used: "estimate_fees"
            Priority fee after multiplier: 7988.09
            Max fee after multiplier: 10270.69
```
