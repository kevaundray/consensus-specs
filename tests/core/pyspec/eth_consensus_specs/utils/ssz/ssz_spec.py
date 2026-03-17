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


BYTES_PER_CHUNK = 32
BYTES_PER_LENGTH_OFFSET = 4
BITS_PER_BYTE = 8


def is_basic_type(typ) -> bool:
    """Check if a type is a basic SSZ type (uintN, boolean, byte)."""
    return issubclass(typ, BasicView)


def size_of(typ) -> int:
    """Return the serialized byte length of a basic type."""
    return typ.type_byte_length()


def is_variable_size(typ) -> bool:
    """Check if a type is variable-size."""
    return not typ.is_fixed_byte_length()


def next_pow_of_two(i: int) -> int:
    """Get the next power of 2 of i, if not already a power of 2. 0 maps to 1."""
    if i <= 1:
        return 1
    return 1 << (i - 1).bit_length()


def chunk_count(typ) -> int:
    """Calculate the number of leaves for merkleization of the type."""
    if is_basic_type(typ):
        return 1
    if issubclass(typ, (Bitvector, Bitlist)):
        if issubclass(typ, Bitvector):
            N = typ.vector_length()
        else:
            N = typ.limit()
        return (N + 255) // 256
    if issubclass(typ, (Vector, List, ByteVector, ByteList)):
        if issubclass(typ, (Vector, ByteVector)):
            N = typ.vector_length()
        else:
            N = typ.limit()
        elem_type = typ.element_cls()
        if is_basic_type(elem_type):
            return (N * size_of(elem_type) + 31) // 32
        else:
            return N
    if issubclass(typ, Container):
        return len(typ.fields())
    raise ValueError(f"chunk_count: unhandled type {typ}")


def serialize_basic(value) -> bytes:
    """Serialize a basic SSZ value (uintN or boolean)."""
    if isinstance(value, boolean):
        return b"\x01" if value else b"\x00"
    elif isinstance(value, uint):
        byte_length = type(value).type_byte_length()
        return int(value).to_bytes(byte_length, "little")
    else:
        raise ValueError(f"serialize_basic: not a basic type: {type(value)}")


def serialize_bitvector(value) -> bytes:
    """Serialize a Bitvector[N]."""
    N = len(value)
    array = [0] * ((N + 7) // 8)
    for i in range(N):
        array[i // 8] |= int(value[i]) << (i % 8)
    return bytes(array)


def serialize_bitlist(value) -> bytes:
    """Serialize a Bitlist[N]. Appends a 1 bit at the end to denote length."""
    length = len(value)
    array = [0] * ((length // 8) + 1)
    for i in range(length):
        array[i // 8] |= int(value[i]) << (i % 8)
    array[length // 8] |= 1 << (length % 8)
    return bytes(array)


def serialize_composite(value) -> bytes:
    """Serialize vectors, containers, lists (fixed and variable-size elements)."""
    if isinstance(value, Container):
        elements = [getattr(value, field) for field in type(value).fields().keys()]
    else:
        elements = list(value)

    # Recursively serialize
    fixed_parts = [serialize(element) if not is_variable_size(type(element)) else None for element in elements]
    variable_parts = [serialize(element) if is_variable_size(type(element)) else b"" for element in elements]

    # Compute and check lengths
    fixed_lengths = [len(part) if part is not None else BYTES_PER_LENGTH_OFFSET for part in fixed_parts]
    variable_lengths = [len(part) for part in variable_parts]
    assert sum(fixed_lengths + variable_lengths) < 2 ** (BYTES_PER_LENGTH_OFFSET * BITS_PER_BYTE)

    # Interleave offsets of variable-size parts with fixed-size parts
    variable_offsets = [
        int.to_bytes(sum(fixed_lengths + variable_lengths[:i]), BYTES_PER_LENGTH_OFFSET, "little")
        for i in range(len(elements))
    ]
    fixed_parts = [part if part is not None else variable_offsets[i] for i, part in enumerate(fixed_parts)]

    # Return the concatenation of the fixed-size parts (offsets interleaved) with the variable-size parts
    return b"".join(fixed_parts + variable_parts)


def serialize_union(value) -> bytes:
    """Serialize a Union type."""
    selector = int(value.selector())
    inner = value.value()
    if inner is None:
        assert selector == 0
        return b"\x00"
    else:
        return selector.to_bytes(1, "little") + serialize(inner)


def serialize_compatible_union(value) -> bytes:
    """Serialize a CompatibleUnion type."""
    selector = int(value.selector())
    return selector.to_bytes(1, "little") + serialize(value.data())


def serialize(value) -> bytes:
    """Serialize an SSZ value to bytes."""
    if isinstance(value, (uint, boolean)):
        return serialize_basic(value)
    elif isinstance(value, Bitvector):
        return serialize_bitvector(value)
    elif isinstance(value, Bitlist):
        return serialize_bitlist(value)
    elif isinstance(value, Union):
        return serialize_union(value)
    elif isinstance(value, (Container, Vector, List)):
        return serialize_composite(value)
    else:
        raise ValueError(f"serialize: unhandled type: {type(value)}")


def pack(values) -> list:
    """Given ordered objects of the same basic type, serialize and pack into chunks."""
    if isinstance(values, BasicView):
        serialized = serialize_basic(values)
    else:
        serialized = b"".join(serialize_basic(v) for v in values)
    # Pad to multiple of BYTES_PER_CHUNK
    if len(serialized) % BYTES_PER_CHUNK != 0:
        serialized += b"\x00" * (BYTES_PER_CHUNK - len(serialized) % BYTES_PER_CHUNK)
    # Partition into chunks
    return [serialized[i:i + BYTES_PER_CHUNK] for i in range(0, len(serialized), BYTES_PER_CHUNK)]


def pack_bits(bits) -> list:
    """Pack bits into bytes (without length delimiter), then into chunks."""
    byte_length = (len(bits) + 7) // 8
    serialized = bytearray(byte_length)
    for i in range(len(bits)):
        serialized[i // 8] |= int(bits[i]) << (i % 8)
    serialized = bytes(serialized)
    if len(serialized) % BYTES_PER_CHUNK != 0:
        serialized += b"\x00" * (BYTES_PER_CHUNK - len(serialized) % BYTES_PER_CHUNK)
    return [serialized[i:i + BYTES_PER_CHUNK] for i in range(0, len(serialized), BYTES_PER_CHUNK)]


def merkleize(chunks: list, limit: int = None) -> bytes:
    """Merkleize chunks into a single root. Pads with zero chunks to next power of two."""
    count = len(chunks)
    if limit is not None:
        assert limit >= count, f"merkleize: input length {count} exceeds limit {limit}"
        num_leaves = next_pow_of_two(limit)
    else:
        num_leaves = next_pow_of_two(count)

    if num_leaves == 0:
        num_leaves = 1

    depth = num_leaves.bit_length() - 1 if num_leaves > 1 else 0

    # Precompute zero hashes for each tree level
    zero_hashes = [b"\x00" * BYTES_PER_CHUNK]
    for _ in range(depth):
        zero_hashes.append(hash(zero_hashes[-1] + zero_hashes[-1]))

    if count == 0:
        return zero_hashes[depth]

    # Build tree bottom-up, using zero hashes for virtual padding
    layer = list(chunks)
    for level in range(depth):
        new_layer = []
        for i in range(0, len(layer), 2):
            left = layer[i]
            right = layer[i + 1] if i + 1 < len(layer) else zero_hashes[level]
            new_layer.append(hash(left + right))
        # If the layer is shorter than expected, pad with precomputed zero hashes
        expected_len = max(1, num_leaves >> (level + 1))
        while len(new_layer) < expected_len:
            new_layer.append(zero_hashes[level + 1])
        layer = new_layer

    return layer[0]


def mix_in_length(root: bytes, length: int) -> bytes:
    """Mix in a length value with a Merkle root."""
    return hash(root + length.to_bytes(BYTES_PER_CHUNK, "little"))


def mix_in_selector(root: bytes, selector: int) -> bytes:
    """Mix in a type selector with a Merkle root."""
    return hash(root + selector.to_bytes(BYTES_PER_CHUNK, "little"))


def hash_tree_root(value) -> bytes:
    """Compute the hash tree root of an SSZ value."""
    typ = type(value)
    if isinstance(value, (uint, boolean)):
        return merkleize(pack(value))
    elif isinstance(value, Bitvector):
        return merkleize(pack_bits(value), limit=chunk_count(typ))
    elif isinstance(value, Bitlist):
        return mix_in_length(
            merkleize(pack_bits(value), limit=chunk_count(typ)),
            len(value),
        )
    elif isinstance(value, Vector):
        if is_basic_type(typ.element_cls()):
            return merkleize(pack(value))
        else:
            return merkleize([hash_tree_root(element) for element in value])
    elif isinstance(value, List):
        if is_basic_type(typ.element_cls()):
            return mix_in_length(
                merkleize(pack(value), limit=chunk_count(typ)),
                len(value),
            )
        else:
            return mix_in_length(
                merkleize(
                    [hash_tree_root(element) for element in value],
                    limit=chunk_count(typ),
                ),
                len(value),
            )
    elif isinstance(value, Container):
        return merkleize([hash_tree_root(getattr(value, field)) for field in typ.fields().keys()])
    elif isinstance(value, Union):
        inner = value.value()
        selector = int(value.selector())
        if inner is None:
            return mix_in_selector(b"\x00" * BYTES_PER_CHUNK, 0)
        else:
            return mix_in_selector(hash_tree_root(inner), selector)
    else:
        raise ValueError(f"hash_tree_root: unhandled type: {typ}")
