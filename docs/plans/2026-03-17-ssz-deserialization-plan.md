# SSZ Deserialization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add executable `deserialize(data, typ)` to the SSZ spec, fully strict with input validation, cross-validated against remerkleable via round-trip and direct comparison.

**Architecture:** Add deserialization functions to `ssz/simple-serialize.md` following the existing serialization pattern. Functions return remerkleable type instances. Cross-validation extends the existing 450-test `test_ssz_cross_validate.py`.

**Tech Stack:** Python, remerkleable (type construction), pytest

**Related:** `docs/plans/2026-03-17-executable-ssz-spec-design.md`, `docs/plans/2026-03-17-executable-ssz-spec-plan.md`

**Key reference files:**

- `tests/core/pyspec/eth_consensus_specs/utils/ssz/ssz_spec.py` — current generated spec (18 functions)
- `tests/core/pyspec/eth_consensus_specs/utils/ssz/ssz_impl.py` — remerkleable wrapper: `deserialize(typ, data)` calls `typ.decode_bytes(data)`
- `tests/core/pyspec/eth_consensus_specs/debug/random_value.py` — shows remerkleable constructor patterns
- `ssz/simple-serialize.md` — the spec to modify

**Remerkleable constructor patterns** (from `random_value.py`):

- `typ(int_value)` for uint types: `uint64(42)`
- `typ(True/False)` for boolean
- `typ(bytes_data)` for ByteVector/ByteList: `typ(b"\x00" * N)`
- `typ(iterable)` for Vector/List/Bitvector/Bitlist: `typ(elem for elem in elements)`
- `typ(**{name: value})` for Container: `typ(foo=uint64(1), bar=boolean(True))`
- `typ(selector=N, value=elem)` for Union

**Note on argument order:** `ssz_impl.deserialize(typ, data)` takes typ first. Our spec function should match: `deserialize(data, typ)` — data first, matching the prose description "deserialize bytes into type". The cross-validation tests will handle the argument order difference.

---

### Task 1: Add deserialization functions to SSZ spec

**Files:**

- Modify: `ssz/simple-serialize.md`
- Regenerate: `tests/core/pyspec/eth_consensus_specs/utils/ssz/ssz_spec.py`

Add the following function definitions to the `## Deserialization` section of the markdown, after the existing prose. Each function goes under its own `#### \`function_name\`` heading.

**Step 1: Add basic and bitfield deserialization**

#### `deserialize_basic`

```python
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
```

#### `deserialize_bitvector`

```python
def deserialize_bitvector(data: bytes, typ):
    """Deserialize a Bitvector[N]."""
    N = typ.vector_length()
    expected_bytes = (N + 7) // 8
    assert len(data) == expected_bytes, f"Expected {expected_bytes} bytes for Bitvector[{N}], got {len(data)}"
    # Check unused high bits are zero
    if N % 8 != 0:
        assert data[-1] >> (N % 8) == 0, "Non-zero padding bits in Bitvector"
    return typ(bool((data[i // 8] >> (i % 8)) & 1) for i in range(N))
```

#### `deserialize_bitlist`

```python
def deserialize_bitlist(data: bytes, typ):
    """Deserialize a Bitlist[N]. Finds the length delimiter bit."""
    assert len(data) >= 1, "Bitlist must have at least 1 byte for length delimiter"
    last_byte = data[-1]
    assert last_byte != 0, "Last byte must have the delimiter bit set"
    # Find delimiter: highest set bit in last byte
    delimiter_index = last_byte.bit_length() - 1
    bit_length = (len(data) - 1) * 8 + delimiter_index
    assert bit_length <= typ.limit(), f"Bitlist length {bit_length} exceeds limit {typ.limit()}"
    return typ(bool((data[i // 8] >> (i % 8)) & 1) for i in range(bit_length))
```

**Step 2: Add composite deserialization**

#### `deserialize_vector`

```python
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
```

#### `deserialize_list`

```python
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
```

#### `deserialize_variable_elements`

```python
def deserialize_variable_elements(data: bytes, elem_type, num_elements: int) -> list:
    """Parse variable-size elements from offset-delimited data."""
    # Read all offsets
    offsets = [
        int.from_bytes(data[i * BYTES_PER_LENGTH_OFFSET:(i + 1) * BYTES_PER_LENGTH_OFFSET], "little")
        for i in range(num_elements)
    ]
    # Validate: first offset must point past the offset region
    assert offsets[0] == num_elements * BYTES_PER_LENGTH_OFFSET, "First offset invalid"
    # Validate: offsets must be non-decreasing and within bounds
    for i in range(len(offsets) - 1):
        assert offsets[i] <= offsets[i + 1], f"Offsets out of order at index {i}"
    assert offsets[-1] <= len(data), f"Last offset {offsets[-1]} exceeds data length {len(data)}"
    # Parse elements using offset boundaries
    elements = []
    for i in range(num_elements):
        start = offsets[i]
        end = offsets[i + 1] if i + 1 < num_elements else len(data)
        elements.append(deserialize(data[start:end], elem_type))
    return elements
```

#### `deserialize_container`

```python
def deserialize_container(data: bytes, typ):
    """Deserialize a Container."""
    field_names = list(typ.fields().keys())
    field_types = list(typ.fields().values())
    if len(field_names) == 0:
        assert len(data) == 0, "Non-empty data for empty container"
        return typ()

    # Calculate fixed region: fixed-size fields take their byte length, variable-size fields take 4 bytes (offset)
    fixed_lengths = [
        BYTES_PER_LENGTH_OFFSET if is_variable_size(ft) else (size_of(ft) if is_basic_type(ft) else ft.type_byte_length())
        for ft in field_types
    ]
    fixed_region_size = sum(fixed_lengths)
    assert len(data) >= fixed_region_size, f"Data too short: {len(data)} < {fixed_region_size}"

    # Parse fixed region
    offsets = []  # (field_index, offset_value) for variable-size fields
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

    # Parse variable-size fields using offsets
    for j, (i, offset) in enumerate(offsets):
        next_offset = offsets[j + 1][1] if j + 1 < len(offsets) else len(data)
        assert offset <= next_offset, f"Offsets out of order for field {field_names[i]}"
        assert next_offset <= len(data), f"Offset out of range for field {field_names[i]}"
        field_values[i] = deserialize(data[offset:next_offset], field_types[i])

    # Construct container
    return typ(**{field_names[i]: field_values[i] for i in range(len(field_names))})
```

#### `deserialize_union`

```python
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
```

**Step 3: Add dispatch function**

#### `deserialize`

```python
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
```

**Step 4: Build and sanity test**

```bash
python -m pysetup.generate_specs --ssz --verbose
```

Verify the new functions are in the generated file:

```bash
grep "^def deserialize" tests/core/pyspec/eth_consensus_specs/utils/ssz/ssz_spec.py
```

Expected: 8 deserialize functions.

Quick sanity test:

```bash
.venv/bin/python -c "
from tests.core.pyspec.eth_consensus_specs.utils.ssz.ssz_spec import serialize, deserialize
from tests.core.pyspec.eth_consensus_specs.utils.ssz.ssz_typing import uint64, boolean
v = uint64(42)
assert deserialize(serialize(v), type(v)) == v
b = boolean(True)
assert deserialize(serialize(b), type(b)) == b
print('Round-trip OK')
"
```

**Step 5: Commit**

```bash
git add ssz/simple-serialize.md
git commit -m "feat(ssz): add executable deserialization functions to SSZ spec"
```

---

### Task 2: Cross-validation tests for deserialization

**Files:**

- Modify: `tests/core/pyspec/eth_consensus_specs/test/phase0/ssz_static/test_ssz_cross_validate.py`

**Step 1: Add deserialization imports**

Add to the existing imports from `ssz_spec`:

```python
from eth_consensus_specs.utils.ssz.ssz_spec import (
    deserialize as spec_deserialize,
    hash_tree_root as spec_hash_tree_root,
    serialize as spec_serialize,
)
```

Add import from `ssz_impl`:

```python
from eth_consensus_specs.utils.ssz.ssz_impl import (
    deserialize as impl_deserialize,
    hash_tree_root,
    serialize,
)
```

**Step 2: Add deserialization assertions to `test_cross_validate_ssz`**

After the existing serialize/hash_tree_root assertions, add:

```python
        # Cross-validate deserialization: round-trip
        spec_roundtrip = spec_deserialize(spec_serialized, ssz_type)
        assert serialize(spec_roundtrip) == impl_serialized, (
            f"Round-trip mismatch for {ssz_type_name} (mode={mode.to_name()}, i={i})"
        )

        # Cross-validate deserialization: compare against remerkleable
        impl_roundtrip = impl_deserialize(ssz_type, impl_serialized)
        assert serialize(spec_roundtrip) == serialize(impl_roundtrip), (
            f"Deserialize mismatch for {ssz_type_name} (mode={mode.to_name()}, i={i})"
        )
```

Note: We compare by re-serializing rather than `==` on objects, since remerkleable object equality may have subtle differences. If both deserialize→serialize produce the same bytes, the deserialization is correct.

**Step 3: Regenerate and run tests**

```bash
make _pyspec
.venv/bin/python -m pytest tests/core/pyspec/eth_consensus_specs/test/phase0/ssz_static/test_ssz_cross_validate.py -x -v --tb=short 2>&1 | tail -20
```

**Step 4: Debug and fix**

Common issues:
- **Constructor patterns:** If `typ(iterable)` doesn't work for some type, try `typ(*list(elements))`
- **ByteVector/ByteList:** May need special handling — remerkleable might expect `bytes` not a generator
- **Empty containers:** Verify `typ()` works for containers with no fields
- **Union options API:** If `typ.options()` returns a dict instead of list, adjust `deserialize_union`

Fix issues in the MARKDOWN, regenerate, re-test.

**Step 5: Run full suite**

```bash
.venv/bin/python -m pytest tests/core/pyspec/eth_consensus_specs/test/phase0/ssz_static/test_ssz_cross_validate.py -v --tb=short 2>&1 | tail -10
```

Expected: 450 passed.

**Step 6: Commit**

```bash
git add tests/core/pyspec/eth_consensus_specs/test/phase0/ssz_static/test_ssz_cross_validate.py ssz/simple-serialize.md
git commit -m "test: cross-validate SSZ deserialization against remerkleable"
```

---

## Checklist

- [ ] Task 1: 8 deserialization functions in simple-serialize.md, builds and sanity-tests
- [ ] Task 2: Cross-validation tests passing for all 450 test cases (round-trip + impl comparison)
