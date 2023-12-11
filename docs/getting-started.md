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

After the installation you can check telliot default configuration by running:

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

The default configuration for `~/telliot/endpoints.yaml` is:

```yaml
type: EndpointList
endpoints:
- type: RPCEndpoint
  chain_id: 943
  network: Pulsechain Testnet
  provider: Pulsechain
  url: https://rpc.v4.testnet.pulsechain.com
  explorer: https://scan.v4.testnet.pulsechain.com/
- type: RPCEndpoint
  chain_id: 369
  network: Pulsechain Mainnet
  provider: Pulsechain
  url: https://rpc.pulsechain.com
  explorer: https://scan.pulsechain.com/
```

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

### telliot-feeds sources

Telliot reporter is configured with default sources. There are default configurations for SpotPrice PLS/USD Query with default PulseX Liquidity Pools (LPs) as price source, these LPs pairs are USDT/WPLS, USDC/WPLS and WPLS/DAI from Pulsechain mainnet. Below is described the default configuration for price sources that use these LPs with the weighted average, time weight average price and volume weighted average price:

- Weighted average: uses the `-qt pls-usd-spot` CLI option for a `telliot report`. It performs the weighted average algorithm for the retrieved prices from the default Liquidity Pool pairs to return one single price.

- Time weight average price (TWAP): uses the `-qt pls-usd-spot-twap-lp` CLI option for a `telliot report`. It performs the TWAP algorithm defined as $twap = \frac{priceCumulative_2 - priceCumulative_1}{timestamp_2 - timestamp_1}$ for the default WPLS/DAI LP pair. The prices cumulative are retrieved from the LP and the default time difference for a TWAP is 30 minutes (1800 seconds).

- Volume weighted average price (VWAP): uses the `-qt pls-usd-spot-vwap` CLI option for a `telliot report`. It performs the TWAP algorithm for each default LP pair, once the prices are retrieved it calculates the weighted average to return one single price.

You can get started with telliot report by running the following telliot command:

```sh
telliot report -a myacct1 -qt pls-usd-spot --fetch-flex
```

It will use default Pulsex Liquidity Pool Pair as price source, please refer to [Configuring price sources](https://github.com/fetchoracle/telliot-feeds/blob/dev/docs/configuring-sources.md) docs to see the default configuration and how to override it.

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

