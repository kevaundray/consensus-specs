# Executable SSZ Type System — Phase 2 Design

## Goal

Replace remerkleable types with spec-defined types, generated from `ssz/ssz-typing.md`. The entire codebase switches transparently via the existing `ssz_typing.py` abstraction layer. Remerkleable stays as a test-only dependency for cross-validation.

## Architecture

```
ssz/ssz-typing.md               (NEW — type system definitions)
ssz/simple-serialize.md          (existing — algorithms)
        |
        v
pysetup/generate_specs.py       (extended — generates both files)
        |
        v
utils/ssz/ssz_typing.py         (REPLACED — generated from spec, not remerkleable re-exports)
utils/ssz/ssz_spec.py           (existing — algorithms, imports from ssz_typing)
```

## Type System

Plain Python backing — dicts for containers, lists for lists/vectors, ints for uints. No tree-backing, no copy-on-write. Parameterized types use `__class_getitem__` with caching.

### Types

**Basic:** `uint` (base), `uint8`/`uint16`/`uint32`/`uint64`/`uint128`/`uint256`, `boolean`, `byte` (alias for `uint8`), `bit` (alias for `boolean`)

**Byte arrays:** `ByteVector[N]`, `ByteList[N]`, `Bytes1`/`Bytes4`/`Bytes8`/`Bytes20`/`Bytes31`/`Bytes32`/`Bytes48`/`Bytes96`

**Collections:** `Vector[T, N]`, `List[T, N]`, `Bitvector[N]`, `Bitlist[N]`

**Composite:** `Container` — subclasses define fields via class annotations, backed by `__slots__`

**Union:** `Union[T0, T1, ...]` — stores selector + value

### Introspection API

Must match what Phase 1 functions use:

- `type_byte_length()` — byte length for fixed-size types (classmethod)
- `is_fixed_byte_length()` — whether type is fixed-size (classmethod)
- `vector_length()` — element count for Vector/Bitvector (classmethod)
- `limit()` — max element count for List/Bitlist/ByteList (classmethod)
- `element_cls()` — element type for List/Vector (classmethod)
- `fields()` — OrderedDict of `{name: type}` for Container (classmethod)
- `options()` — type options for Union (classmethod)

### Instance behavior

- Construction: `uint64(42)`, `boolean(True)`, `Container(**fields)`, `List[uint64, 4](1, 2, 3)`
- Field access: `container.field_name`
- Indexing: `vector[0]`, `list_val[i]`
- Length: `len(list_val)`, `len(bitvector)`
- Iteration: `for elem in vector`
- `isinstance`/`issubclass` checks must work for type dispatch in Phase 1 functions

## Source format

`ssz/ssz-typing.md` — markdown with Python code blocks. Classes use `@dataclass` decorator so the `md_to_spec.py` parser stores them in `spec["dataclasses"]` (avoids the heading-name check in `_process_code_class`).

## Build pipeline

New `generate_ssz_typing()` function in `generate_specs.py` (separate from `generate_ssz_spec()`). Assembles: imports + classes + helper functions + type aliases. Called alongside `generate_ssz_spec()` when `--all-forks` or `--ssz` is passed.

## Transition

`ssz_typing.py` switches from remerkleable re-exports to generated spec types. Same exported names — no downstream changes needed. Remerkleable stays as test dependency for cross-validation.

## Testing

**Type-system unit tests** (`test_ssz_typing.py`):
- Parameterization caching
- Construction patterns
- Field access, indexing, iteration
- Introspection API
- isinstance/issubclass dispatch

**Cross-validation** (existing 450 tests):
- Construct objects with new types
- Compare serialize/deserialize/hash_tree_root against remerkleable
- Cross-validation imports remerkleable directly (not via ssz_typing)

## Migration phases within Phase 2

1. Write `ssz/ssz-typing.md` with all type definitions
2. Add `generate_ssz_typing()` to build pipeline
3. Unit test the type system in isolation
4. Swap `ssz_typing.py` to generated version
5. Run full cross-validation suite
6. Fix any compatibility issues
