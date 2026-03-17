from .base import BaseSpecBuilder


class SszSpecBuilder(BaseSpecBuilder):
    @property
    def fork(self) -> str:
        return "ssz"

    @classmethod
    def imports(cls, preset_name: str) -> str:
        return """
from eth_consensus_specs.utils.ssz.ssz_typing import (
    BasicView,
    Bitlist,
    Bitvector,
    boolean,
    ByteList,
    ByteVector,
    Container,
    List,
    uint,
    uint32,
    Union,
    Vector,
)
from eth_consensus_specs.utils.hash_function import hash
"""
