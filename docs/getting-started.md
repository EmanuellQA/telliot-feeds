# Getting Started

## Prerequisites
- An account with your chain's native token for gas fees. Testnets often have a faucet. For example, [here is Pulsechain's ](https://faucet.v4.testnet.pulsechain.com/) for testnet V4.
- [Python 3.9](https://www.python.org/downloads/release/python-3915/) is required to install and use `telliot-feeds`. Alternatively, you can use our [docker](https://docs.docker.com/get-started/) release. If using Docker, please follow the [Docker setup instructions](#optional-docker-setup).


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

    git clone git@github.com:fetchoracle/telliot-feeds.git
    git clone git@github.com:fetchoracle/telliot-core.git

After that, install telliot core:

    cd telliot-core
    pip install -e .
    pip install -r requirements-dev.txt


Finally, install telliot feeds:

    cd ../telliot-feeds
    pip install -e .
    pip install -r requirements-dev.txt


*If your log shows no errors, that's it! Next, follow the instructions for [configuring telliot](#telliot-configuration).*

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
git clone git@github.com:fetchoracle/telliot-feeds.git
git clone git@github.com:fetchoracle/telliot-core.git
```
2. Create & start container in background:
```
sudo docker compose -f telliot-feeds/docker-compose.yml up -d
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

