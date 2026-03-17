"""Cross-validate the executable SSZ spec (ssz_spec.py) against remerkleable (ssz_impl.py).

For every Container type defined in the phase0 spec, generates random instances
using various randomization modes, then asserts that serialize() and hash_tree_root()
produce identical results between both implementations.
"""

import hashlib
from inspect import getmembers, isclass
from random import Random

import pytest

from eth_consensus_specs.debug import random_value
from eth_consensus_specs.test.context import spec_targets
from eth_consensus_specs.test.helpers.constants import MINIMAL, PHASE0
from eth_consensus_specs.utils.ssz.ssz_impl import (
    hash_tree_root,
    serialize,
)
from eth_consensus_specs.utils.ssz.ssz_spec import (
    hash_tree_root as spec_hash_tree_root,
    serialize as spec_serialize,
)
from eth_consensus_specs.utils.ssz.ssz_typing import Container, ProgressiveContainer

MAX_BYTES_LENGTH = 1000
MAX_LIST_LENGTH = 10


def _get_phase0_ssz_type_names():
    """Get all SSZ container type names from the phase0 minimal spec."""
    spec = spec_targets[MINIMAL][PHASE0]
    return [
        name
        for (name, value) in getmembers(spec, isclass)
        if issubclass(value, Container | ProgressiveContainer)
        and value != Container
        and value != ProgressiveContainer
    ]


def _deterministic_seed(**kwargs) -> int:
    """Deterministic seed that is consistent between runs."""
    m = hashlib.sha256()
    for k, v in sorted(kwargs.items()):
        m.update(f"{k}={v}".encode())
    return int.from_bytes(m.digest()[:8], "little")


SSZ_TYPE_NAMES = _get_phase0_ssz_type_names()

MODES = [
    random_value.RandomizationMode.mode_zero,
    random_value.RandomizationMode.mode_max,
    random_value.RandomizationMode.mode_nil_count,
    random_value.RandomizationMode.mode_one_count,
    random_value.RandomizationMode.mode_max_count,
    random_value.RandomizationMode.mode_random,
]


@pytest.mark.parametrize("ssz_type_name", SSZ_TYPE_NAMES)
@pytest.mark.parametrize(
    "mode", MODES, ids=[m.to_name() for m in MODES]
)
def test_cross_validate_ssz(ssz_type_name, mode, preset=MINIMAL):
    """Cross-validate serialize and hash_tree_root between spec and impl."""
    spec = spec_targets[preset][PHASE0]
    ssz_type = getattr(spec, ssz_type_name)

    count = 3 if mode.is_changing() else 1
    for i in range(count):
        seed = _deterministic_seed(
            ssz_type_name=ssz_type_name,
            mode=mode.to_name(),
            i=i,
        )
        rng = Random(seed)
        value = random_value.get_random_ssz_object(
            rng, ssz_type, MAX_BYTES_LENGTH, MAX_LIST_LENGTH, mode, chaos=False
        )

        # Cross-validate serialization
        impl_serialized = serialize(value)
        spec_serialized = spec_serialize(value)
        assert spec_serialized == impl_serialized, (
            f"Serialize mismatch for {ssz_type_name} (mode={mode.to_name()}, i={i}): "
            f"spec={spec_serialized[:20].hex()}... impl={impl_serialized[:20].hex()}..."
        )

        # Cross-validate hash_tree_root
        impl_root = hash_tree_root(value)
        spec_root = spec_hash_tree_root(value)
        assert bytes(spec_root) == bytes(impl_root), (
            f"hash_tree_root mismatch for {ssz_type_name} (mode={mode.to_name()}, i={i}): "
            f"spec={bytes(spec_root).hex()} impl={bytes(impl_root).hex()}"
        )
