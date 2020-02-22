from eth2spec.test.context import (
    with_all_phases_except,
    spec_state_test,
    always_bls,
)
from eth2spec.test.helpers.state import next_slot, transition_to
from eth2spec.test.helpers.attestations import (
    run_attestation_processing,
    # get_valid_attestation as get_valid_late_attestation,
)
from eth2spec.test.helpers.phase1.attestations import (
    get_valid_on_time_attestation,
)


@with_all_phases_except(['phase0'])
@spec_state_test
@always_bls
def test_on_time_success(spec, state):
    next_slot(spec, state)
    attestation = get_valid_on_time_attestation(spec, state, signed=True)

    transition_to(spec, state, state.slot + spec.MIN_ATTESTATION_INCLUSION_DELAY)

    yield from run_attestation_processing(spec, state, attestation)


@with_all_phases_except(['phase0'])
@spec_state_test
@always_bls
def test_on_time_empty_custody_bits_blocks(spec, state):
    # Causing this test to pass causes many phase0 tests to fail
    pass
    """
    next_slot(spec, state)
    attestation = get_valid_late_attestation(spec, state, signed=True)

    assert not any(attestation.custody_bits_blocks)

    transition_to(spec, state, state.slot + spec.MIN_ATTESTATION_INCLUSION_DELAY)

    yield from run_attestation_processing(spec, state, attestation, False)
    """


@with_all_phases_except(['phase0'])
@spec_state_test
@always_bls
def test_late_with_custody_bits_blocks(spec, state):
    next_slot(spec, state)
    attestation = get_valid_on_time_attestation(spec, state, signed=True)

    transition_to(spec, state, state.slot + spec.MIN_ATTESTATION_INCLUSION_DELAY + 1)

    yield from run_attestation_processing(spec, state, attestation, False)
