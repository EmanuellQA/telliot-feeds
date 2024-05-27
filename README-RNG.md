# Fetch Random Number Generator
Fetch Random Number Generator is based on Tellor Rng [https://tellor.io/blog/tellor-rng/] which uses a timestamp (in the past) as a seed for generating random numbers using the block hashes from both networks. FetchRNG differs from Tellor in that it uses the Ethereum and Pulsechain networks to generate random numbers.

## Requirements:
 You need to setup ETHERSCAN_API_KEY in telliot .env file in order to RNG feeds to work

There are two approaches for using a random number generator in Fetch:

The first one is a more decentralized version, based on the same concepts as TellorRNG where a timestamp is required to generate a random number and every queryid is different due to the fact that the parameters for the random number generation are included in the QueryData information.

 for instance, a query data for FetchRNG is contructed in the following way:


```
 abi.encode("FetchRNG", abi.encode(1715300772))
 then for each timestamp seed, a new query id will be created (because the query id is the keccak256 hash of the query data)
```

The options for a consumer of this type of feed is required to request (and tip) in advance the specific timestamp that would seed a random number

 For reporting a single random number using a FetchRNG feed, specifying a timestamp, you can execute the following command in telliot:


```
 telliot report -a YOUR_ACCOUNT --rng-timestamp THE_SEED_TIMESTAMP -ncr --fetch-flex --submit-once
 Another option is to setup a reporter based on intervals, for this you need to setup a timestamp for a start interval and the interval size (in seconds) and telliot will report a new random number in every interval.
```

please take into consideration that you need to setup INTERVAL and START_TIME in your telliot .env file


```
telliot report -a YOUR_ACCOUNT --rng-timestamp THE_SEED_TIMESTAMP -ncr --fetch-flex
```

 A third option could be using the tip scanner in order to detect the tips for specific timestamps and only report when a tip is send to a specific query.

2. The second option is based on a feed stream of random numbers, similar to using SpotPrice feeds, these feeds does not change the queryid, Moreover, this option is compatible with managed feeds.

 For instance, a query data for FetchRNGCustom is contructed in the following way:

```
 abi.encode("FetchRNGCustom", abi.encode("name", 1715300772))
```

 This feed includes the interval setting and a name inside of the QueryData

 please take into consideration that you need to setup INTERVAL, FETCH_RNG_NAME and START_TIME in your telliot .env file after setting up the enviroment variables, you can report using the following telliot command:

```
 telliot report -a YOUR_ACCOUNT -qt fetch-rng-custom --fetch-flex
```

 FetchRNGCustom feeds return two values as a result, the first is a bytes32 field which is the random number generated, the second one is the timestamp seed used.

 FetchRNGCustom feeds are suitable for use cases that require a stream of random numbers. However take into consideration the following restrictions:

The interval should not be less than the average block size (around 13 seconds) otherwise the generation of random numbers will be ineffective.

There is a risk of reporters sending the same report, in order to avoid this, reduce the number of reporter to avoid clashes.

