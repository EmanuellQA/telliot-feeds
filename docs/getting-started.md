# Getting Started

## Prerequisites
- An account with your chain's native token for gas fees. Testnets often have a faucet. For example, [here is Pulsechain's ](https://faucet.v4.testnet.pulsechain.com/) for testnet V4.
- A Linux distribution or macOS on your machine, as they are both Unix-based. **Windows is currently not supported.**
- [Python 3.9](https://www.python.org/downloads/release/python-3915/) is required to install and use `telliot-feeds`. Please refer to [Install Python 3.9 using pyenv](#install-python-39-using-pyenv) section if you have a different Python version in your system. Alternatively, you can use our [docker](https://docs.docker.com/get-started/) release. If using Docker, please follow the [Docker setup instructions](#optional-docker-setup).

## Use the stable environment

Please switch to the stable environment by using the production-ready branch for Telliot:
```sh
git checkout main
```

## Install Python 3.9 using pyenv

[Pyenv](https://github.com/pyenv/pyenv) is a Python version manager that lets you easily switch between multiple versions of Python. Using pyenv, you don't need to uninstall the Python version you have installed to use version 3.9, thus avoiding problems with applications that rely on your current version. Following the documentation, this pyenv setup guide is for Ubuntu:

1. Install pyenv dependencies

    ```sh
    sudo apt update; sudo apt install build-essential libssl-dev zlib1g-dev \
    libbz2-dev libreadline-dev libsqlite3-dev curl \
    libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev
    ```

2. Execute the pyenv installer

    ```sh
    curl https://pyenv.run | bash
    ```

3. Add these commands into your `~/.bashrc` file.

    ```sh
    echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
    echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
    echo 'eval "$(pyenv init -)"' >> ~/.bashrc
    ```

    These commands will define an environment variable PYENV_ROOT to point to the path where Pyenv will store its data (default in `$HOME/.pyenv`); add the pyenv executable to your PATH;  install pyenv into your shell as a shell function to enable shims and autocompletion.

4. Restart your shell

    ```sh
    exec "$SHELL"
    ```

5. Install Python 3.9 and select Python 3.9 globally

    ```sh
    pyenv install 3.9
    pyenv global 3.9
    ```

Please refer to the [pyenv wiki documentation](https://github.com/pyenv/pyenv/wiki) for troubleshooting.

## Install Telliot Feeds

It's generally considered good practice to run telliot from a python [virtual environment](https://docs.python.org/3/library/venv.html). This is not required, but it helps prevent dependency conflicts with other Python programs running on your computer. 

In this example, the virtual environment will be created in a subfolder called `tenv`:

=== "Linux"

    ```
    python3.9 -m venv tenv
    source tenv/bin/activate
    ```

=== "Windows"

    ```
    py3.9 -m venv tenv
    tenv\Scripts\activate
    ```

=== "Mac M1"

    ```
    python3.9 -m venv tenv
    source tenv/bin/activate
    ```

Once the virtual environment is activated, install telliot from the source code. First, clone telliot feeds and telliot core repositories in the same folder:

    git clone https://github.com/fetchoracle/telliot-feeds.git
    git clone https://github.com/fetchoracle/telliot-core.git

After that, install telliot core:

    cd telliot-core
    pip install -e .
    pip install -r requirements-dev.txt


Finally, install telliot feeds:

    cd ../telliot-feeds
    pip install -e .
    pip install -r requirements.txt

During the installation, the package `eth-brownie` may log errors about dependencies version conflict. It will not compromise the installation, it happens because that package pushes some packages' versions downwards whereas there are packages that require newer versions.

After the installtion you can check telliot installtion by running:

```sh
telliot config show
```

After the installation, follow the instructions for [configuring telliot](#telliot-configuration).*

## (Optional) Docker Setup
*Skip this section if you already have Python 3.9 and and the correct dependencies installed.*
*This Docker Setup guide is for Linux Ubuntu. The commands will be different for Windows, Mac, and other Linux distros.*
### Prerequisites
- Linux Ubuntu 20.04
- Follow the Step 1 instructions [here](https://www.digitalocean.com/community/tutorials/how-to-install-and-use-docker-on-ubuntu-20-04) for installing Docker on Linux Ubuntu. For example, an Ubuntu AWS instance (t2.medium) with the following specs:
    - Ubuntu 20.04
    - 2 vCPUs
    - 4 GB RAM
- Install Docker Compose & Docker CLI:
    ```
    sudo apt-get install docker-ce docker-ce-cli containerd.io docker-compose-plugin
    ```

*If you get permission errors with the Ubuntu install commands or using docker, run them as root with `sudo ` prefixed to your command.*

### Install Telliot Feeds Using Docker
Use the following commands to create and run a container with the correct Python version and dependencies to configure and run Telliot:

1. clone telliot feeds and telliot core repositories in the same folder:

```
git clone https://github.com/fetchoracle/telliot-feeds.git
git clone https://github.com/fetchoracle/telliot-core.git
```
2. Create & start container in background:
```
sudo docker compose -f docker-compose.yml up -d
```
3. Open shell to container: 
```
sudo docker exec -it telliot_container sh
```
4. Next [configure telliot](#telliot-configuration) inside the container. To close shell to the container run: `exit`. If you exit the shell, the container will still be running in the background, so you can open a new shell to the container at any time with the command above. This is useful if running telliot from a remote server like an AWS instance. You can close the shell and disconnect from the server, but the container can still be running Telliot in the background.

## Telliot Configuration

After installation, Telliot must be personalized to use your own private keys and endpoints.

First, create the default configuration files:

    telliot config init

The default configuration files are created in a folder called `telliot` in the user's home folder.

To view your current configuration at any time:

    telliot config show

### Add Reporting Accounts

The reporter (telliot) needs to know which accounts (wallet addresses) are available for submitting values to the oracle.
Use the command line to add necessary reporting accounts/private keys.

For example, to add an account called `myacct1` for reporting on Pulsechain testnet v4 (chain ID 943). You'll need to replace the private key in this example with the private key that holds your FETCH for reporting:

    >> telliot account add myacct1 0x57fe7105302229455bcfd58a8b531b532d7a2bb3b50e1026afa455cd332bf706 943
    Enter encryption password for myacct1: 
    Confirm password: 
    Added new account myacct1 (address= 0xcd19cf65af3a3aea1f44a7cb0257fc7455f245f0) for use on chains (943,)

To view other options for managing accounts with telliot, use the command:
    
        telliot account --help

After adding accounts, [configure your endpoints](#configure-endpoints).

### Configure endpoints

You can add your RPC endpoints via the command line or by editing the `endpoints.yaml` file. It's easier to do via the command line, but here's an example command using the [nano](https://www.nano-editor.org/) text editor to edit the YAML file directly:
    
    nano ~/telliot/endpoints.yaml

[Optional] Run `set_telliot_env.py` script to set Telliot environment. That script will configure local `telliot-core` to use `ENV_NAME` environment variable when selecting the `contract_directory.<ENV_NAME>.json` contracts directory file.

The supported environments are testnet and mainnet.Execute `python set_telliot_env.py --help` for details:

```sh
python set_telliot_env.py --env testnet
```

### Configuring telliot-feeds sources environment variables

Open the [.env.example](https://github.com/fetchoracle/telliot-feeds/blob/main/.env.example) file so that you can review the config for the reporter. You can use these defaults to report to `mainnet`.

These environment variables configure which source will be used to Spot a Price. Using a different source will report a different values.

- Query PLS/USD (`-qt pls-usd-spot`)

    The SpotPrice for pls-usd-spot query-tag can use one of three sources: `PulsechainPulseXSource`, `CoinGeckoSpotPriceSource` or `PulsechainSubgraphSource`.
    
    The feed [pls_usd_feed.py](https://github.com/fetchoracle/telliot-feeds/blob/dev/src/telliot_feeds/feeds/pls_usd_feed.py) checks the environment variable in the `.env` file for its respective sources. If it finds a config for `PLS_CURRENCY_SOURCES`, it uses the `PulsechainPulseXSource` and passes its data to a Price Aggregator using the weighted average algorithm. Otherwise, it checks for `COINGECKO_MOCK_URL` to use the CoinGecko as source. Finally, if it does not find either configuration, it uses the default Pulsechain Subgraph as source, the variable `PULSECHAIN_SUBGRAPH_URL` configures the subgraph URL.
    
    The `PulsechainPulseXSource` also requires the `PLS_ADDR_SOURCES` environment variable, which are the contract addresses for the given `PLS_CURRENCY_SOURCES`; the `PLS_LPS_ORDER` variable, which tells the currency order of the Liquidity pool since the `PulsechainPulseXSource` needs to know if it is a "WPLS/DAI" or "DAI/WPLS" Liquidity Pool for example; and the `LP_PULSE_NETWORK_URL`, it configures the `PulsechainPulseXSource` URL to pulse mainnet or pulse testnet to interact with the Pool contract.

- Query FETCH/USD (`-qt fetch-usd-pot`)

    The SpotPrice for fetch-usd-spot query-tag can use one of two sources: `PulseXSupgraphSource` or `CoinGeckoSpotPriceSource`.

    The feed [fetch_usd_feed.py](https://github.com/fetchoracle/telliot-feeds/blob/dev/src/telliot_feeds/feeds/fetch_usd_feed.py) checks the environment variables in the `.env` file for its respective sources. If it finds a config for `PULSEX_SUBGRAPH_URL` it uses the PulseX Supgraph as source. Otherwise, it uses the default CoinGecko source. The `PulseXSupgraphSource` also requires the `FETCH_ADDRESS` environment variable.

- Query PLSX/USD (`qt plsx-usd-spot`)

    The SpotPrice for plsx-usd-spot query-tag only users `PulsechainPulseXSource` source.

    The feed [plsx_usd_feed.py](https://github.com/fetchoracle/telliot-feeds/blob/dev/src/telliot_feeds/feeds/plsx_usd_feed.py) will use the configuration for `PLSX_CURRENCY_SOURCES`, `PLSX_ADDR_SOURCES` and `PLSX_LPS_ORDER` likewise for pls-sd-spot.

The currency sources supported for pls-usd-spot and plsx-usd-spot are "DAI", "USDC" and "USDT".

### Configure endpoint via CLI

To configure your endpoint via the CLI, use the `report` command and enter `n` when asked if you want to keep the default settings:
```
$ telliot report -a myacct1 --fetch-flex
INFO    | telliot_core | telliot-core 0.2.3dev0
INFO    | telliot_core | Connected to PulseChain Testnet-V4 [default account: myacct1], time: 2023-05-23 23:47:06.014174
Your current settings...
Your chain id: 943

Your Pulsechain Testnet endpoint: 
 - provider: Pulsechain
 - RPC url: https://rpc.v4.testnet.pulsechain.com
 - explorer url: https://scan.v4.testnet.pulsechain.com
Your account: myacct1 at address 0x1234...
Proceed with current settings (y) or update (n)? [Y/n]:
...
```
Once you enter your endpoint via the CLI, it will be saved in the `endpoints.yaml` file.

To skip reporting after you've updated your configuration, press `Ctrl+C` to exit once it prompts you to confirm your settings:
```
...
Press [ENTER] to confirm settings.
...
```

If you don't have your own node URL, a free RPC one can be obtained at [Pulsechain.com](http://pulsechain.com).  

**Once you've added an endpoint, you can read the [Usage](./usage.md) section,
then you'll be set to report.**

