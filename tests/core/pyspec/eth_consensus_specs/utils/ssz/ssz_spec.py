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
    if issubclass(typ, (ByteVector, ByteList)):
        if issubclass(typ, ByteVector):
            N = typ.vector_length()
        else:
            N = typ.limit()
        return (N + 31) // 32
    if issubclass(typ, (Vector, List)):
        if issubclass(typ, Vector):
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
    elif isinstance(value, (ByteVector, ByteList)):
        return bytes(value)
    elif isinstance(value, Union):
        return serialize_union(value)
    elif isinstance(value, (Container, Vector, List)):
        return serialize_composite(value)
    else:
        raise ValueError(f"serialize: unhandled type: {type(value)}")


def deserialize_basic(data: bytes, typ):
    """Deserialize a basic SSZ value (uintN or boolean)."""
    expected_length = size_of(typ)
    assert len(data) == expected_length, f"Expected {expected_length} bytes, got {len(data)}"
    if issubclass(typ, boolean):
        assert data in (b"\x00", b"\x01"), f"Invalid boolean value: 0x{data.hex()}"
        return typ(data == b"\x01")
    elif issubclass(typ, uint):
        return typ(int.from_bytes(data, "little"))
    else:
        raise ValueError(f"deserialize_basic: not a basic type: {typ}")


def deserialize_bitvector(data: bytes, typ):
    """Deserialize a Bitvector[N]."""
    N = int(typ.vector_length())
    expected_bytes = (N + 7) // 8
    assert len(data) == expected_bytes, f"Expected {expected_bytes} bytes for Bitvector[{N}], got {len(data)}"
    if N % 8 != 0:
        assert data[-1] >> (N % 8) == 0, "Non-zero padding bits in Bitvector"
    return typ(bool((data[i // 8] >> (i % 8)) & 1) for i in range(N))


def deserialize_bitlist(data: bytes, typ):
    """Deserialize a Bitlist[N]. Finds the length delimiter bit."""
    assert len(data) >= 1, "Bitlist must have at least 1 byte for length delimiter"
    last_byte = data[-1]
    assert last_byte != 0, "Last byte must have the delimiter bit set"
    delimiter_index = last_byte.bit_length() - 1
    bit_length = (len(data) - 1) * 8 + delimiter_index
    assert bit_length <= typ.limit(), f"Bitlist length {bit_length} exceeds limit {typ.limit()}"
    return typ(bool((data[i // 8] >> (i % 8)) & 1) for i in range(bit_length))


def deserialize_vector(data: bytes, typ):
    """Deserialize a Vector[T, N]."""
    elem_type = typ.element_cls()
    length = typ.vector_length()
    if is_variable_size(elem_type):
        return typ(deserialize_variable_elements(data, elem_type, length))
    else:
        elem_size = size_of(elem_type) if is_basic_type(elem_type) else elem_type.type_byte_length()
        assert len(data) == length * elem_size, (
            f"Expected {length * elem_size} bytes for Vector of {length} elements, got {len(data)}"
        )
        return typ(deserialize(data[i * elem_size:(i + 1) * elem_size], elem_type) for i in range(length))


def deserialize_list(data: bytes, typ):
    """Deserialize a List[T, N]."""
    elem_type = typ.element_cls()
    if len(data) == 0:
        return typ()
    if is_variable_size(elem_type):
        assert len(data) >= BYTES_PER_LENGTH_OFFSET, "Data too short for variable-size list"
        first_offset = int.from_bytes(data[:BYTES_PER_LENGTH_OFFSET], "little")
        assert first_offset % BYTES_PER_LENGTH_OFFSET == 0, "First offset not aligned"
        num_elements = first_offset // BYTES_PER_LENGTH_OFFSET
        assert num_elements <= typ.limit(), f"List length {num_elements} exceeds limit {typ.limit()}"
        return typ(deserialize_variable_elements(data, elem_type, num_elements))
    else:
        elem_size = size_of(elem_type) if is_basic_type(elem_type) else elem_type.type_byte_length()
        assert len(data) % elem_size == 0, f"Data length {len(data)} not aligned to element size {elem_size}"
        num_elements = len(data) // elem_size
        assert num_elements <= typ.limit(), f"List length {num_elements} exceeds limit {typ.limit()}"
        return typ(deserialize(data[i * elem_size:(i + 1) * elem_size], elem_type) for i in range(num_elements))


def deserialize_variable_elements(data: bytes, elem_type, num_elements: int) -> list:
    """Parse variable-size elements from offset-delimited data."""
    offsets = [
        int.from_bytes(data[i * BYTES_PER_LENGTH_OFFSET:(i + 1) * BYTES_PER_LENGTH_OFFSET], "little")
        for i in range(num_elements)
    ]
    assert offsets[0] == num_elements * BYTES_PER_LENGTH_OFFSET, "First offset invalid"
    for i in range(len(offsets) - 1):
        assert offsets[i] <= offsets[i + 1], f"Offsets out of order at index {i}"
    assert offsets[-1] <= len(data), f"Last offset {offsets[-1]} exceeds data length {len(data)}"
    elements = []
    for i in range(num_elements):
        start = offsets[i]
        end = offsets[i + 1] if i + 1 < num_elements else len(data)
        elements.append(deserialize(data[start:end], elem_type))
    return elements


def deserialize_container(data: bytes, typ):
    """Deserialize a Container."""
    field_names = list(typ.fields().keys())
    field_types = list(typ.fields().values())
    if len(field_names) == 0:
        assert len(data) == 0, "Non-empty data for empty container"
        return typ()

    fixed_lengths = [
        BYTES_PER_LENGTH_OFFSET if is_variable_size(ft) else (size_of(ft) if is_basic_type(ft) else ft.type_byte_length())
        for ft in field_types
    ]
    fixed_region_size = sum(fixed_lengths)
    assert len(data) >= fixed_region_size, f"Data too short: {len(data)} < {fixed_region_size}"

    offsets = []
    field_values = {}
    pos = 0
    for i, ft in enumerate(field_types):
        if is_variable_size(ft):
            offset = int.from_bytes(data[pos:pos + BYTES_PER_LENGTH_OFFSET], "little")
            offsets.append((i, offset))
            pos += BYTES_PER_LENGTH_OFFSET
        else:
            field_values[i] = deserialize(data[pos:pos + fixed_lengths[i]], ft)
            pos += fixed_lengths[i]

    for j, (i, offset) in enumerate(offsets):
        next_offset = offsets[j + 1][1] if j + 1 < len(offsets) else len(data)
        assert offset <= next_offset, f"Offsets out of order for field {field_names[i]}"
        assert next_offset <= len(data), f"Offset out of range for field {field_names[i]}"
        field_values[i] = deserialize(data[offset:next_offset], field_types[i])

    return typ(**{field_names[i]: field_values[i] for i in range(len(field_names))})


def deserialize_union(data: bytes, typ):
    """Deserialize a Union type."""
    assert len(data) >= 1, "Union must have at least 1 byte for selector"
    selector = data[0]
    options = typ.options()
    assert selector < len(options), f"Invalid union selector {selector}, only {len(options)} options"
    if options[selector] is None:
        assert len(data) == 1, "None union variant must be exactly 1 byte"
        return typ(selector=selector, value=None)
    inner = deserialize(data[1:], options[selector])
    return typ(selector=selector, value=inner)


def deserialize(data: bytes, typ):
    """Deserialize SSZ bytes into a value of the given type."""
    if issubclass(typ, (uint, boolean)):
        return deserialize_basic(data, typ)
    elif issubclass(typ, Bitvector):
        return deserialize_bitvector(data, typ)
    elif issubclass(typ, Bitlist):
        return deserialize_bitlist(data, typ)
    elif issubclass(typ, ByteVector):
        assert len(data) == typ.vector_length(), (
            f"Expected {typ.vector_length()} bytes for ByteVector, got {len(data)}"
        )
        return typ(data)
    elif issubclass(typ, ByteList):
        assert len(data) <= typ.limit(), f"ByteList length {len(data)} exceeds limit {typ.limit()}"
        return typ(data)
    elif issubclass(typ, Union):
        return deserialize_union(data, typ)
    elif issubclass(typ, Container):
        return deserialize_container(data, typ)
    elif issubclass(typ, Vector):
        return deserialize_vector(data, typ)
    elif issubclass(typ, List):
        return deserialize_list(data, typ)
    else:
        raise ValueError(f"deserialize: unhandled type: {typ}")


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


def pack_bytes(value) -> list:
    """Pack a ByteVector or ByteList (raw bytes) into chunks."""
    serialized = bytes(value)
    if len(serialized) == 0:
        return []
    # Pad to multiple of BYTES_PER_CHUNK
    if len(serialized) % BYTES_PER_CHUNK != 0:
        serialized += b"\x00" * (BYTES_PER_CHUNK - len(serialized) % BYTES_PER_CHUNK)
    # Partition into chunks
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
            new_layer.append(hash(bytes(left) + bytes(right)))
        layer = new_layer
        # If the layer is empty (all virtual), use the precomputed zero hash
        if len(layer) == 0:
            return zero_hashes[depth]

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
    elif isinstance(value, ByteVector):
        return merkleize(pack_bytes(value))
    elif isinstance(value, ByteList):
        return mix_in_length(
            merkleize(pack_bytes(value), limit=chunk_count(typ)),
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
