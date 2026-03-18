# Executable SSZ Spec Design

## Goal

Make `/ssz/simple-serialize.md` an executable spec — extracted by the same `pysetup` pipeline that processes fork specs — producing a standalone Python module. This replaces the current reliance on remerkleable for SSZ algorithms, while keeping remerkleable as a validation oracle until explicitly removed.

## Architecture

```
ssz/simple-serialize.md          (source of truth — markdown with Python)
        |
        v
pysetup/md_to_spec.py            (existing extraction, no changes)
pysetup/spec_builders/ssz.py     (new, minimal — just imports)
        |
        v
utils/ssz/ssz_spec.py            (generated executable spec)
        |
        v
utils/ssz/ssz_impl.py            (existing — delegates to remerkleable)
utils/ssz/ssz_typing.py          (existing — re-exports remerkleable types)
```

Both `ssz_spec.py` and `ssz_impl.py` coexist. Existing SSZ tests run against both and assert identical results. The executable spec operates on remerkleable types as input during Phase 1.

## Approach: Follow polynomial-commitments.md Pattern

The SSZ spec will be restructured to match the pattern of `specs/deneb/polynomial-commitments.md`:
- Constants in standard markdown tables
- All algorithms as proper `def function_name(...)` definitions
- Each function under its own heading with explanatory prose

The existing `md_to_spec.py` parser handles this without modification. The `SszSpecBuilder` is near-trivial — just an `imports()` method providing access to remerkleable types.

## SSZ Spec Restructuring

The current code blocks in `simple-serialize.md` are bare snippets (e.g., `return value.to_bytes(...)`). These become proper function definitions.

### Functions to define

**Serialization:**
- `serialize(value)` — dispatch function
- Type-specific: `serialize_uint`, `serialize_boolean`, `serialize_bitvector`, `serialize_bitlist`, `serialize_container`, `serialize_union`, `serialize_compatible_union`

**Deserialization:**
- `deserialize(data, typ)` — dispatch function
- Type-specific helpers mirroring serialization

**Merkleization helpers:**
- `pack(values)`, `pack_bits(bits)`
- `next_pow_of_two(i)`
- `merkleize(chunks, limit=None)`, `merkleize_progressive(chunks, num_leaves=1)`
- `mix_in_length`, `mix_in_selector`, `mix_in_active_fields`
- `chunk_count(typ)`, `size_of(typ)`, `is_variable_size(typ)`

**Top-level:**
- `hash_tree_root(value)`

### Type coverage (Phase 1)

All standard SSZ types: `uintN`, `boolean`, `Container`, `Vector`, `List`, `Bitvector`, `Bitlist`, `Union`.

Progressive types (`ProgressiveContainer`, `ProgressiveList`, `ProgressiveBitlist`, `CompatibleUnion`) deferred to a follow-up.

Merkle proofs (`merkle-proofs.md`) also deferred.

## Build Pipeline Changes

### New files
- `pysetup/spec_builders/ssz.py` — `SszSpecBuilder` with `imports()` method

### Modified files
- `pysetup/md_doc_paths.py` — add SSZ spec entry (separate from fork document lists)
- `pysetup/generate_specs.py` — add step to generate SSZ module (runs alongside fork specs)

### No changes needed
- `pysetup/md_to_spec.py` — existing parser handles the restructured markdown as-is

### Output
- `tests/core/pyspec/eth_consensus_specs/utils/ssz/ssz_spec.py` — generated module

## Validation Strategy

Extend existing SSZ tests (`ssz_static`, `ssz_generic`) to run against both implementations:

- `ssz_spec.hash_tree_root(obj) == ssz_impl.hash_tree_root(obj)` for every test case
- `ssz_spec.serialize(obj) == ssz_impl.ssz_serialize(obj)` for every test case
- Round-trip: `deserialize(serialize(obj), type(obj)) == obj`

No new test infrastructure — additional assertions in existing test cases. The test suite already covers all beacon chain SSZ types with multiple randomization modes (zero, max, random, chaos, etc.).

## Migration Phases

### Phase 1 — Executable algorithms, validated against remerkleable

- Restructure `simple-serialize.md` with proper function definitions
- Add `SszSpecBuilder` and wire into build pipeline
- Generated `ssz_spec.py` lives next to `ssz_impl.py`
- Existing tests gain comparison assertions
- All production code still uses remerkleable
- No risk — new code is exercised but not relied upon

### Phase 2 — Executable type system, validated against remerkleable

- Build `Container`, `List`, `Vector`, etc. in the executable spec
- Full SSZ stack (types + algorithms) lives in the spec
- Tests run both implementations, asserting identical results
- Remerkleable stays as validation oracle

### Phase 3 — Remove remerkleable (gated on explicit approval)

- Do not proceed until explicitly approved
- Drop remerkleable dependency
- `ssz_impl.py` and `ssz_typing.py` delegate to spec-defined code
