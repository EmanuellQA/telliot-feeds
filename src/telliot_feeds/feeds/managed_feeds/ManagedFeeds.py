from typing import Union, TypedDict
from pathlib import Path

import yaml

class ManagedFeedConfig(TypedDict):
    pair: str
    asset: str
    currency: str

class ManagedFeeds:
    def __init__(self):
        self.managed_feeds_config_path = Path.joinpath(
            Path(__file__).parent, 'managed_feeds.yaml'
        ).resolve()
    
    def _get_managed_feeds(self) -> Union[list[ManagedFeedConfig], None]:
        try:
            with open(self.managed_feeds_config_path, 'r') as file:
                data = yaml.safe_load(file)
            return data['managed-feeds']
        except Exception as e:
            error_messages = {
                FileNotFoundError: "'managed_feeds.yaml' config file not found: {}",
                KeyError: "'managed-feeds' key not found in managed_feeds.yaml: {}"
            }
            error_message = error_messages.get(type(e), "Unexpected error reading managed_feeds.yaml config file: {}")
            print(error_message.format(e))
            return None

    def _get_assets(self) -> list[str]:
        managed_feeds = self._get_managed_feeds()
        
        if managed_feeds is None:
            return []
        
        return [feed['asset'] for feed in managed_feeds]

    @property
    def assets(self) -> list[str]:
        return self._get_assets()

managed_feeds = ManagedFeeds()
