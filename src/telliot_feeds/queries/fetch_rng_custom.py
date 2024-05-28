import logging
from dataclasses import field, dataclass
from hexbytes import HexBytes
from telliot_feeds.dtypes.value_type import ValueType
from telliot_feeds.queries.abi_query import AbiQuery

from eth_abi import decode_abi
from eth_abi import encode_abi

logger = logging.getLogger(__name__)

@dataclass
class FetchRNGCustomReturnType(ValueType):

    abi_type: str = "(bytes32,ufixed256x18)"

    def encode(self, value: tuple) -> bytes:
        """An encoder for Fetch RNG response type

        Encodes a tuple of float values.
        """
        if len(value) != 2 or not isinstance(value[0], HexBytes) or not isinstance(value[1], int):
            raise ValueError("Invalid response type")

        return encode_abi(["bytes32", "uint256"], value)

    def decode(self, bytes_val: bytes) -> tuple:
        """A decoder for for Fetch RNG response type

        Decodes a tuple of float values.
        """
        return decode_abi(["bytes32", "uint256"], bytes_val)

@dataclass
class FetchRNGCustom(AbiQuery):
    """Returns a pseudorandom number generated from hashing together blockhashes from multiple chains.

    Attributes:
        name: 
            name of the custom rng feed
        timestamp:
            time at which to take the most recent blockhashes (example: 1647624359)
    """
    is_custom_rng: bool = field(default=True, init=False)
    is_managed_feed: bool = field(default=True, init=False)

    name: str
    interval: int

    #: ABI used for encoding/decoding parameters
    abi = [
        {"name": "name", "type": "string"},
        {"name": "interval", "type": "uint256"}
    ]

    @property
    def value_type(self) -> ValueType:
        """Data type returned for a FetchRNG query.

        - `bytes32`: 32 bytes hexadecimal value
        - `packed`: false
        """
        #return ValueType(abi_type="bytes32", packed=False)
        return FetchRNGCustomReturnType()