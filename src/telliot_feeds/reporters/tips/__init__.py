import logging
from typing import Optional

from multicall.constants import MULTICALL2_ADDRESSES
from multicall.constants import MULTICALL3_ADDRESSES
from multicall.constants import Network
from multicall.constants import NO_STATE_OVERRIDE

from telliot_feeds.queries.query_catalog import query_catalog

logger = logging.getLogger(__name__)


# add testnet support for multicall that aren't avaialable in the package
def add_multicall_support(
    network: str,
    network_id: int,
    state_override: bool = True,
    multicall2_address: Optional[str] = None,
    multicall3_address: Optional[str] = None,
) -> None:
    """Add support for a network that doesn't have multicall support in the package"""
    if not hasattr(Network, network):
        setattr(Network, network, network_id)
        attr = getattr(Network, network)
        if not state_override:
            # Gnosis chain doesn't have state override so we need to add it
            # to the list of chains that don't have state override in the package
            # to avoid errors
            NO_STATE_OVERRIDE.append(attr)
        if multicall2_address:
            MULTICALL2_ADDRESSES[attr] = multicall2_address
        else:
            MULTICALL3_ADDRESSES[attr] = multicall3_address
    else:
        print(f"Network {network} already exists in multicall package")

add_multicall_support(
    network="PulsechainTestnet v4", network_id=943, multicall3_address="0x207cc7e2141Db4244BE07093CAf5df9a089128F2"
)

add_multicall_support(
    network="PulsechainMainnet", network_id=369, multicall3_address="0xca11bde05977b3631167028862be2a173976ca11"
)

add_multicall_support(
    network="Chiado",
    network_id=10200,
    state_override=False,
    multicall3_address="0x08e08170712c7751b45b38865B97A50855c8ab13",
)
CATALOG_QUERY_IDS = {query_catalog._entries[tag].query.query_id: tag for tag in query_catalog._entries}
CATALOG_QUERY_DATA = {query_catalog._entries[tag].query.query_data: tag for tag in query_catalog._entries}
