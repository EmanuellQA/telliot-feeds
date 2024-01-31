import time
import threading
from web3 import Web3

class Contract:
    ABI = """
    [
    {
        "anonymous": false,
        "inputs": [
            {
                "indexed": false,
                "internalType": "uint112",
                "name": "reserve0",
                "type": "uint112"
            },
            {
                "indexed": false,
                "internalType": "uint112",
                "name": "reserve1",
                "type": "uint112"
            }
        ],
        "name": "Sync",
        "type": "event"
    }
    ]
    """
    ADDRESS = "0xE56043671df55dE5CDf8459710433C10324DE0aE"

    def __init__(self) -> None:
        self.provider_url = "http://0.0.0.0:8545"
        self.w3 = Web3(Web3.HTTPProvider(self.provider_url))
        self.account = self.w3.eth.account.from_key("0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d")

    def _get_contract(self):
        return self.w3.eth.contract(address=self.ADDRESS, abi=self.ABI)
    
class ListenLPContract(Contract):
    def __init__(self) -> None:
        super().__init__()
        self.lp_contract = self._get_contract()
        self.is_looging = False

    def _log_loop(self, event_filter, threading_some_event, polling_interval=8):
        blue_color = "\033[94m"
        endc_color = "\033[0m"
        while True:
            for event in event_filter.get_new_entries():
                print(blue_color)
                print("LP EVENT:")
                print(event)
                print(endc_color)
                threading_some_event.set()
                # todo add event to a queue or something (which the main thread can read from)
            time.sleep(polling_interval)

    def listen_sync_events(self, threading_some_event):
        event_filter = self.lp_contract.events.Sync.createFilter(fromBlock='latest')
        th = threading.Thread(target=self._log_loop, args=(event_filter,threading_some_event), daemon=True)
        blue_color = "\033[94m"
        endc_color = "\033[0m"
        th.start()
        print(f"{blue_color}Started listening to LP contract events{endc_color}")