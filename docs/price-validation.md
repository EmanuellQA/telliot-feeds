# Price validation

For managed feeds we can pass additional flags for price validation, these are `-pvc` (`--price-validation-consensus`) and `-pvm` (`--price-validation-method`) usage example:

```sh
telliot report -a <account> -qt validated-feed-usd-spot -ncr --fetch-flex -gm 40 --use-estimate-fee -pvc majority -pvm percentage_change
```

Both the shorter versions (`-pvc` and `-pvm`) and the longer versions (`--price-validation-consensus` and `--price-validation-method`) of these variables can be used.

The acceptable string values for `-pvc` are one of `any`, `majority` and `all`. It will be used as a query parameter to the Price validator service endpoint. Please, see the [Price Service](https://github.com/fetchoracle/price-services/) documentation for the price validator endpoints reference.

The `-pvc` variable tells the price validator how the price should be evaluated as valid or not in a consensus of its price services. The price validator has a set of price services responsible for retrieving a price. For example, a set of its price services are Coingecko, Coinpaprika, Coinmarketcap and Liquidity Pools LWAP. Each of these price services is going to return a value for the spot of the PLS/USD pair. If the `--price-validation-consensus` is passed as `-pvc any` for example, if at least of one these services evaluates that the price submitted by Telliot is valid (i.e. close to the value retrieved by the price service), the validator will return the price as a valid price. Using `-pvc all` requires all price services to judge the price submitted by Telliot as a valid price, and using `-pvc majority` requires the majority of them. How to tell if a price submitted is close to a price service or not is controlled by the `-pvm` and `PRICE_TOLERANCE` variables described below.

Price validation also requires an environment variable setup, `PRICE_TOLERANCE`, in the `telliot-feeds/.env` file.

The acceptable string values for `-pvm` are one of `percentage_change`, `percentage_difference` and `absolute_difference`. It will also be used as a query parameter for the price service.

Percentage change algorithm - $\frac{|PriceSubmitted - PriceService|}{PriceService} * 100$

Percentage difference algorithm - $\frac{|PriceSubmitted - PriceService|}{\frac{PriceSubmitted + PriceService}{2}} * 100 $

Absolute difference algorithm - $|PriceSubmitted - PriceService|$

The default price validation method is the `percentage_change` and the default consensus method is the `majority`. The `PRICE_TOLERANCE` environment variable tells the tolerance, so that once we have the result of a validation method the validator evaluates if the price is valid or not. For example, given that Telliot is going to submit a PLS/USD price as 0.00014, but the Coingecko price service retrieved the price as 0.00013122, the percentage change of these values is:

$\frac{|0.00014 - 0.00013122|}{0.00013122} * 100 = 6.691053193110791$

If the percentage result of 6.691053193110791 is within the `PRICE_TOLERANCE` tolerance the price is evaluated as valid. For instance, if the setup was `PRICE_TOLERANCE="0.07"` (7%) the price would be valid, but if it was less than 6.69 it would not be valid.

A log showing this validation information retrieved from the price service is presented in Telliot, in the following example the price validator is running on localhost:

```sh
Price Validator Service API info:
Request URL: http://127.0.0.1:3333/validate-price?price=0.00013189637369191059&tolerance=0.104&validation-method=percentage_change&consensus=majority
Validation method: percentage_change
Consensus: majority
Tolerance: 0.104
services result: [{'service_name': 'Coingecko', 'service_price': 0.00013381, 'result': 1.4301070981910242, 'is_valid': False}, {'service_name': 'Coinpaprika', 'service_price': 0.000134689285241476, 'result': 2.073595939393538, 'is_valid': False}, {'service_name': 'Coinmarketcap', 'service_price': 0.00013977345159278757, 'result': 5.635603765317225, 'is_valid': False}, {'service_name': 'LWAP', 'service_price': 0.00013189637369191059, 'result': 0.0, 'is_valid': True}]
Telliot Price: 0.00013189637369191059
Is valid consensus: False
```

the `tolerance=0.104` comes from the `PRICE_TOLERANCE="0.00104"` (0.104%) `telliot-feeds/.env` variable, the validation method as percentage_change comes from `-pvm percentage_change` and the consensus method from the `-pvc majority` variable.

The example above shows that using a tolerance of 0.104 for percentage change it's too precise, a percentage of 5% would cause the Coingecko service to evaluate as valid (since 1.4301070981910242 is less than or equal to 5), the Coinpaprika and the LWAP as well, only the Coinmarketcap service would tell that the price of 0.00013189637369191059 submitted from Telliot is not valid, and the consensus majority would evaluate as a valid price. Note that if we had chosen the `-pvc any` the consensus in the example above would be valid, since it needs at least one and the LWAP service evaluates as a valid price.

Therefore, the price validator used by Telliot can be configured according to the values passed to `-pvc` (consensus, any, majority or all), `-pvm` (calculation method, percentage change, percentage difference or absolute difference) and the `PRICE_TOLERANCE` environment variable. Using higher values for `PRICE_TOLERANCE` makes the validator more tolerant of price differences, this variable is related to the method chosen, the percentage change in the example above was 6.69%, but the absolute difference would be 0.00000878 (8.78 × 10^-6), using the absolute difference would evaluate the price as valid since 0.00000878 <= 0.104. 
