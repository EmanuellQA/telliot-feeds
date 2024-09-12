import logging
from dataclasses import dataclass

from telliot_feeds.dtypes.value_type import ValueType
from telliot_feeds.queries.abi_query import AbiQuery

logger = logging.getLogger(__name__)


@dataclass
class FetchOracleAddress(AbiQuery):
    """Returns the latest Fetch oracle address.
    It is used for updating the time based rewards recipient on mainnet.

    Attributes:
        phantom:
            Empty bytes, always used for query types with no arguments

    See the data spec for more info about this query type:
    https://github.com/fetchoracle/dataSpecs/blob/main/types/FetchOracleAddress.md
    """

    @property
    def value_type(self) -> ValueType:
        """Data type returned for a FetchOracleAddress query.

        - `address`: the address of the Fetch oracle
        - `packed`: false
        """

        return ValueType(abi_type="address", packed=False)
