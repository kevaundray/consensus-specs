# Executable SSZ Spec — Phase 1 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `ssz/simple-serialize.md` executable through the existing `pysetup` pipeline, generating `ssz_spec.py` with `serialize` and `hash_tree_root` functions that produce identical results to remerkleable.

**Architecture:** Restructure the SSZ spec markdown to contain proper Python function definitions (same pattern as `specs/deneb/polynomial-commitments.md`). A new `SszSpecBuilder` provides imports. A new `generate_ssz_spec()` function in `generate_specs.py` parses the markdown and assembles the output module. Existing SSZ tests cross-validate against remerkleable.

**Tech Stack:** Python 3.12+, marko (markdown parser), remerkleable (SSZ library — used for type introspection only), pytest

**Design doc:** `docs/plans/2026-03-17-executable-ssz-spec-design.md`

**Key reference files:**

- `specs/deneb/polynomial-commitments.md` — model for how an algorithm spec should look
- `pysetup/spec_builders/base.py` — BaseSpecBuilder abstract class (all methods are classmethods)
- `pysetup/spec_builders/phase0.py` — example builder showing imports pattern
- `pysetup/spec_builders/__init__.py` — builder registry
- `pysetup/generate_specs.py` — spec generation pipeline
- `pysetup/md_to_spec.py` — markdown parser (extracts Python from code blocks via AST)
- `tests/core/pyspec/eth_consensus_specs/utils/ssz/ssz_impl.py` — current remerkleable wrapper (38 lines)
- `tests/core/pyspec/eth_consensus_specs/utils/ssz/ssz_typing.py` — re-exports remerkleable types
- `tests/core/pyspec/eth_consensus_specs/debug/random_value.py` — shows remerkleable type introspection API
- `tests/core/pyspec/eth_consensus_specs/debug/encode.py` — shows remerkleable instance access patterns
- `tests/core/pyspec/eth_consensus_specs/test/phase0/ssz_static/test_ssz_static.py` — SSZ test suite

**Remerkleable type introspection API** (from `random_value.py` and `encode.py`):

- `issubclass(typ, uint)` / `isinstance(value, uint)` — check uint types
- `typ.type_byte_length()` — byte length of basic/fixed types
- `typ.vector_length()` — element count for Vector/Bitvector
- `typ.limit()` — max element count for List/Bitlist/ByteList
- `typ.element_cls()` — element type for List/Vector
- `typ.fields()` — OrderedDict of `{field_name: field_type}` for Container
- `typ.is_fixed_byte_length()` — whether type has fixed serialized size
- `typ.options()` — list of type options for Union; dict of `{selector: type}` for CompatibleUnion
- `getattr(value, field_name)` — access container field value
- `value.value()` — inner value for Union (method call, not property)
- `value.selector()` — selector for Union/CompatibleUnion (method call)
- `value.data()` — inner data for CompatibleUnion (method call)
- `len(value)` — current length for List/Bitlist
- `for element in value` — iterate elements of List/Vector/Bitvector/Bitlist
- `value[i]` — index access

---

### Task 1: Build Infrastructure

**Files:**

- Create: `pysetup/spec_builders/ssz.py`
- Modify: `pysetup/spec_builders/__init__.py`
- Modify: `pysetup/constants.py`
- Modify: `pysetup/generate_specs.py`

**Step 1: Add SSZ constant to `pysetup/constants.py`**

Add after the existing fork constants (after line 11, the `EIP8025` line):

```python
SSZ = "ssz"
```

**Step 2: Create `pysetup/spec_builders/ssz.py`**

```python
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
```

**Step 3: Register builder in `pysetup/spec_builders/__init__.py`**

Add import:

```python
from .ssz import SszSpecBuilder
```

Add to the `spec_builders` dict (after the existing entries):

```python
SszSpecBuilder,
```

Note: the SSZ builder is registered here for `generate_ssz_spec()` to access via import, but SSZ is NOT a fork and should NOT be in `PREVIOUS_FORK_OF` or `ALL_FORKS`.

**Step 4: Add `generate_ssz_spec()` to `pysetup/generate_specs.py`**

Add this function after `generate_fork_specs()` (after line 249):

```python
def generate_ssz_spec(out_dir: Path, verbose: bool = False) -> None:
    """
    Generate the executable SSZ spec module from ssz/simple-serialize.md.

    Unlike fork specs, SSZ has no presets, configs, or fork lineage.
    The output is a single Python module with constants and functions.
    """
    from pysetup.spec_builders.ssz import SszSpecBuilder

    source_file = Path("ssz/simple-serialize.md")
    if not source_file.exists():
        raise FileNotFoundError(f"SSZ spec not found: {source_file}")

    if verbose:
        print(f"Generating SSZ spec from: {source_file}")

    # Parse with empty preset/config — SSZ has neither
    spec_object = MarkdownToSpec(source_file, preset={}, config={}, preset_name="").run()

    # Assemble module: imports + constants + functions
    imports = SszSpecBuilder.imports("").strip()

    constants = "\n".join(
        f"{name} = {vardef.value}"
        for name, vardef in spec_object.constant_vars.items()
    )

    functions = "\n\n\n".join(spec_object.functions.values())

    spec_str = "\n\n\n".join(filter(None, [imports, constants, functions])) + "\n"

    # Write output
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "ssz_spec.py"
    out_file.write_text(spec_str)

    if verbose:
        print(f"  Wrote: {out_file} ({len(spec_str):,} bytes)")
```

**Step 5: Wire into `main()` in `pysetup/generate_specs.py`**

Add a new CLI argument (after the `--verbose` argument, around line 312):

```python
parser.add_argument(
    "--ssz",
    action="store_true",
    help="Generate executable SSZ spec module",
)
```

In the `try` block of `main()`, after the fork generation loop (after line 347), add:

```python
# Generate SSZ spec if requested
if args.all_forks or getattr(args, 'ssz', False):
    ssz_out_dir = Path("tests/core/pyspec/eth_consensus_specs/utils/ssz")
    generate_ssz_spec(ssz_out_dir, verbose=args.verbose)
```

**Step 6: Commit**

```bash
git add pysetup/constants.py pysetup/spec_builders/ssz.py pysetup/spec_builders/__init__.py pysetup/generate_specs.py
git commit -m "feat: add SszSpecBuilder and SSZ generation pipeline"
```

---

### Task 2: Restructure SSZ Spec — Helper Functions

**Files:**

- Modify: `ssz/simple-serialize.md`

The current code blocks in `simple-serialize.md` are bare snippets (e.g., `return value.to_bytes(...)`) that would fail the `md_to_spec.py` parser, which expects `FunctionDef` or `ClassDef` AST nodes.

We restructure the spec by:
1. Replacing bare code blocks with proper function definitions
2. Adding a new "Helpers" section with utility functions
3. Verifying example code blocks in list items (Typing section) are NOT parsed as top-level elements

**Important parser behavior:** `md_to_spec.py` iterates over `document.children` (top-level elements only). Code blocks nested inside list items (like the `ContainerExample` class in the Typing section) are children of the list item, not the document. They should be ignored by the parser. Verify this during implementation — if the parser does pick them up, add `<!-- eth_consensus_specs: skip -->` before each example code block.

**Step 1: Add a Helpers section after the Typing section**

Insert a new `## Helpers` section between `## Typing` and `## Serialization`. Add these function definitions, each under its own heading with a backtick-wrapped name:

#### `is_basic_type`

```python
def is_basic_type(typ) -> bool:
    """Check if a type is a basic SSZ type (uintN, boolean, byte)."""
    return issubclass(typ, BasicView)
```

#### `size_of`

```python
def size_of(typ) -> int:
    """Return the serialized byte length of a basic type."""
    return typ.type_byte_length()
```

#### `is_variable_size`

```python
def is_variable_size(typ) -> bool:
    """Check if a type is variable-size (recursive for composites)."""
    return not typ.is_fixed_byte_length()
```

Note: this delegates to remerkleable's `is_fixed_byte_length()`. This is type introspection, not algorithm — acceptable in Phase 1.

#### `next_pow_of_two`

```python
def next_pow_of_two(i: int) -> int:
    """Get the next power of 2 of i, if not already a power of 2. 0 maps to 1."""
    if i <= 1:
        return 1
    return 1 << (i - 1).bit_length()
```

#### `chunk_count`

```python
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
```

**Step 2: Test the build with just helpers**

```bash
python -m pysetup.generate_specs --ssz --verbose
```

Expected: generates `tests/core/pyspec/eth_consensus_specs/utils/ssz/ssz_spec.py` containing the imports, constants (`BYTES_PER_CHUNK`, `BYTES_PER_LENGTH_OFFSET`, `BITS_PER_BYTE`), and the helper functions.

If the build fails due to example code blocks in the Typing section being parsed, add `<!-- eth_consensus_specs: skip -->` comments before each example code block.

**Step 3: Commit**

```bash
git add ssz/simple-serialize.md
git commit -m "feat(ssz): add executable helper functions to SSZ spec"
```

---

### Task 3: Restructure SSZ Spec — Serialization

**Files:**

- Modify: `ssz/simple-serialize.md`

Replace ALL existing bare code blocks in the `## Serialization` section with proper function definitions. The old bare snippets (e.g., `return value.to_bytes(...)`) are removed and replaced with the functions below.

Keep the prose descriptions above each code block — they explain the algorithm. Just replace the code blocks themselves.

**Step 1: Add serialization functions**

Replace the code blocks under the Serialization section headings with these functions:

#### `serialize_basic`

Replace the `uintN` and `boolean` code blocks with a single function:

```python
def serialize_basic(value) -> bytes:
    """Serialize a basic SSZ value (uintN or boolean)."""
    if isinstance(value, boolean):
        return b"\x01" if value else b"\x00"
    elif isinstance(value, uint):
        byte_length = type(value).type_byte_length()
        return int(value).to_bytes(byte_length, "little")
    else:
        raise ValueError(f"serialize_basic: not a basic type: {type(value)}")
```

#### `serialize_bitvector`

Replace the `Bitvector[N]` code block:

```python
def serialize_bitvector(value) -> bytes:
    """Serialize a Bitvector[N]."""
    N = len(value)
    array = [0] * ((N + 7) // 8)
    for i in range(N):
        array[i // 8] |= int(value[i]) << (i % 8)
    return bytes(array)
```

#### `serialize_bitlist`

Replace the `Bitlist[N]` code block:

```python
def serialize_bitlist(value) -> bytes:
    """Serialize a Bitlist[N]. Appends a 1 bit at the end to denote length."""
    length = len(value)
    array = [0] * ((length // 8) + 1)
    for i in range(length):
        array[i // 8] |= int(value[i]) << (i % 8)
    array[length // 8] |= 1 << (length % 8)
    return bytes(array)
```

#### `serialize_composite`

Replace the vectors/containers/lists code block:

```python
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
```

#### `serialize_union`

Replace the Union code block:

```python
def serialize_union(value) -> bytes:
    """Serialize a Union type."""
    selector = int(value.selector())
    inner = value.value()
    if inner is None:
        assert selector == 0
        return b"\x00"
    else:
        return selector.to_bytes(1, "little") + serialize(inner)
```

#### `serialize`

Add a new dispatch function (this is the main entry point):

```python
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
```

Note: `ByteVector` and `ByteList` are subclasses of `Vector` and `List` respectively, so they're handled by `serialize_composite`.

**Step 2: Build and verify**

```bash
python -m pysetup.generate_specs --ssz --verbose
```

Inspect the generated file:

```bash
head -80 tests/core/pyspec/eth_consensus_specs/utils/ssz/ssz_spec.py
```

Verify it contains all the serialization functions.

**Step 3: Quick sanity test**

```bash
cd /home/kev/work/consensus-specs
python -c "
from tests.core.pyspec.eth_consensus_specs.utils.ssz.ssz_spec import serialize, serialize_basic
from tests.core.pyspec.eth_consensus_specs.utils.ssz.ssz_typing import uint64, boolean
print(serialize(uint64(42)).hex())
print(serialize(boolean(True)).hex())
print('OK')
"
```

Expected: `2a00000000000000`, `01`, `OK`

**Step 4: Commit**

```bash
git add ssz/simple-serialize.md
git commit -m "feat(ssz): add executable serialization functions to SSZ spec"
```

---

### Task 4: Restructure SSZ Spec — Merkleization

**Files:**

- Modify: `ssz/simple-serialize.md`

The current `## Merkleization` section has prose descriptions with mathematical notation. Replace them with proper function definitions while keeping the explanatory prose above each code block.

**Step 1: Add merkleization helper functions**

#### `pack`

```python
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
```

#### `pack_bits`

```python
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
```

#### `merkleize`

```python
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
```

Note: `hash()` comes from `eth_consensus_specs.utils.hash_function` (SHA-256, returns `Bytes32`). Verify that `Bytes32 + Bytes32` concatenation works. If not, cast with `bytes()`: `hash(bytes(left) + bytes(right))`.

#### `mix_in_length`

```python
def mix_in_length(root: bytes, length: int) -> bytes:
    """Mix in a length value with a Merkle root."""
    return hash(root + length.to_bytes(BYTES_PER_CHUNK, "little"))
```

#### `mix_in_selector`

```python
def mix_in_selector(root: bytes, selector: int) -> bytes:
    """Mix in a type selector with a Merkle root."""
    return hash(root + selector.to_bytes(BYTES_PER_CHUNK, "little"))
```

**Step 2: Add `hash_tree_root`**

```python
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
```

Note: `ByteVector`/`ByteList` are subclasses of `Vector`/`List` and handled by those branches. Their `element_cls()` returns `byte` (a basic type), so the `is_basic_type` branch applies correctly.

**Step 3: Build and verify**

```bash
python -m pysetup.generate_specs --ssz --verbose
```

**Step 4: Sanity test merkleization**

```bash
python -c "
from tests.core.pyspec.eth_consensus_specs.utils.ssz.ssz_spec import hash_tree_root as spec_htr
from tests.core.pyspec.eth_consensus_specs.utils.ssz.ssz_impl import hash_tree_root as impl_htr
from tests.core.pyspec.eth_consensus_specs.utils.ssz.ssz_typing import uint64, boolean, Container

# Test basic types
v = uint64(42)
print(f'spec: {bytes(spec_htr(v)).hex()}')
print(f'impl: {bytes(impl_htr(v)).hex()}')
assert bytes(spec_htr(v)) == bytes(impl_htr(v)), 'MISMATCH on uint64'

b = boolean(True)
assert bytes(spec_htr(b)) == bytes(impl_htr(b)), 'MISMATCH on boolean'

print('Basic types OK')
"
```

Expected: both produce identical hex output, `Basic types OK`.

**Step 5: Commit**

```bash
git add ssz/simple-serialize.md
git commit -m "feat(ssz): add executable merkleization and hash_tree_root to SSZ spec"
```

---

### Task 5: Cross-Validation Tests

**Files:**

- Modify: `tests/core/pyspec/eth_consensus_specs/test/phase0/ssz_static/test_ssz_static.py`

**Step 1: Add imports for the executable SSZ spec**

At the top of `test_ssz_static.py`, add alongside the existing ssz_impl imports (after line 18):

```python
from eth_consensus_specs.utils.ssz.ssz_spec import (
    hash_tree_root as spec_hash_tree_root,
    serialize as spec_serialize,
)
```

**Step 2: Add comparison assertions to the test template**

In the `the_test` function inside `_template_ssz_static_tests` (around line 69-72), after the existing yields:

```python
        yield "value", "data", encode.encode(value)
        yield "serialized", "ssz", serialize(value)
        roots_data = {"root": "0x" + hash_tree_root(value).hex()}
        yield "roots", "data", roots_data
```

Add cross-validation assertions:

```python
        # Cross-validate executable SSZ spec against remerkleable
        spec_serialized = spec_serialize(value)
        assert spec_serialized == serialize(value), (
            f"Serialize mismatch for {ssz_type_name}: "
            f"spec={spec_serialized[:20].hex()}... impl={serialize(value)[:20].hex()}..."
        )
        spec_root = spec_hash_tree_root(value)
        assert bytes(spec_root) == bytes(hash_tree_root(value)), (
            f"hash_tree_root mismatch for {ssz_type_name}: "
            f"spec={bytes(spec_root).hex()} impl={bytes(hash_tree_root(value)).hex()}"
        )
```

**Step 3: Run the SSZ static tests**

First regenerate specs (SSZ spec module must exist):

```bash
make _pyspec
```

Then run just the SSZ static tests with a small subset:

```bash
python -m pytest tests/core/pyspec/eth_consensus_specs/test/phase0/ssz_static/ \
    -k "ssz_random_minimal" --preset=minimal -x -v --tb=short 2>&1 | head -60
```

`-x` stops at first failure. Start small, fix any mismatches.

**Step 4: Debug mismatches**

Common issues to watch for:

- **`Bytes32` concatenation:** If `hash(Bytes32 + Bytes32)` fails, wrap with `bytes()` in the merkleize function
- **`boolean` bit operations:** If `int(value[i])` fails for Bitvector/Bitlist, try `1 if value[i] else 0`
- **`ByteVector`/`ByteList` iteration:** If iterating over a ByteVector yields raw bytes instead of uint8 views, adjust `pack()` to handle both
- **Union dispatch order:** Ensure `isinstance(value, Union)` is checked BEFORE `isinstance(value, Container)` — Union might be a subclass of Container in remerkleable (unlikely but check)

**Step 5: Run full SSZ test suite**

```bash
python -m pytest tests/core/pyspec/eth_consensus_specs/test/phase0/ssz_static/ \
    --preset=minimal -v --tb=short
```

Then with mainnet preset:

```bash
python -m pytest tests/core/pyspec/eth_consensus_specs/test/phase0/ssz_static/ \
    --preset=mainnet -v --tb=short
```

**Step 6: Commit**

```bash
git add tests/core/pyspec/eth_consensus_specs/test/phase0/ssz_static/test_ssz_static.py
git commit -m "test: cross-validate executable SSZ spec against remerkleable"
```

---

### Task 6: Deserialization (follow-up)

> This task is deferred. Complete Tasks 1-5 first. Serialization + hash_tree_root provide the core cross-validation. Deserialization can be added once the core is stable.

The approach:

- Add `deserialize(data, typ)` dispatch function and type-specific helpers to the spec
- Validate with round-trip tests: `deserialize(serialize(obj), type(obj)) == obj`
- Most complex part is variable-size composite deserialization (offset parsing)
- Reference: the "Deserialization" prose section in `simple-serialize.md` describes the algorithm

---

## Checklist

- [ ] Task 1: SszSpecBuilder + generate_ssz_spec() + CLI wiring
- [ ] Task 2: Helpers (is_basic_type, size_of, is_variable_size, next_pow_of_two, chunk_count)
- [ ] Task 3: Serialization (serialize_basic, serialize_bitvector, serialize_bitlist, serialize_composite, serialize_union, serialize)
- [ ] Task 4: Merkleization (pack, pack_bits, merkleize, mix_in_length, mix_in_selector, hash_tree_root)
- [ ] Task 5: Cross-validation tests passing for all SSZ types
- [ ] Task 6: Deserialization (deferred)
