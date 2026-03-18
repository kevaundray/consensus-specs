from typing import TypeVar

from .ssz_spec import (
    deserialize as _spec_deserialize,
    hash_tree_root as _spec_hash_tree_root,
    serialize as _spec_serialize,
)
from .ssz_typing import Bytes32, View, uint


def ssz_serialize(obj: View) -> bytes:
    return _spec_serialize(obj)


def serialize(obj: View) -> bytes:
    return ssz_serialize(obj)


def ssz_deserialize(typ: type, data: bytes):
    return _spec_deserialize(data, typ)


def deserialize(typ: type, data: bytes):
    return ssz_deserialize(typ, data)


def hash_tree_root(obj: View) -> Bytes32:
    return Bytes32(_spec_hash_tree_root(obj))


def uint_to_bytes(n) -> bytes:
    if isinstance(n, uint):
        return _spec_serialize(n)
    # Plain int: serialize as uint64 (default width, matching remerkleable behavior)
    return int(n).to_bytes(8, "little")


V = TypeVar("V", bound=View)


def copy(obj: V) -> V:
    return obj.copy()
