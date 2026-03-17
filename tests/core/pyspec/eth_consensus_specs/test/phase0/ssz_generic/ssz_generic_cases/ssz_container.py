from collections.abc import Callable, Sequence
from random import Random

from eth_consensus_specs.debug.random_value import get_random_ssz_object, RandomizationMode
from eth_consensus_specs.test.exceptions import SkippedTest
from eth_consensus_specs.utils.ssz.ssz_impl import deserialize, serialize
from eth_consensus_specs.utils.ssz.ssz_typing import (
    Bitlist,
    Bitvector,
    byte,
    ByteList,
    Container,
    List,
    ProgressiveBitlist,
    ProgressiveList,
    uint8,
    uint16,
    uint32,
    uint64,
    Vector,
    View,
)

from .ssz_test_case import invalid_test_case, valid_test_case


class SingleFieldTestStruct(Container):
    A: byte


class SmallTestStruct(Container):
    A: uint16
    B: uint16


class FixedTestStruct(Container):
    A: uint8
    B: uint64
    C: uint32


class VarTestStruct(Container):
    A: uint16
    B: List[uint16, 1024]
    C: uint8


class ComplexTestStruct(Container):
    A: uint16
    B: List[uint16, 128]
    C: uint8
    D: ByteList[256]
    E: VarTestStruct
    F: Vector[FixedTestStruct, 4]
    G: Vector[VarTestStruct, 2]


class ContainerListTestStruct(Container):
    A: uint16
    B: List[VarTestStruct, 8]
    C: uint8


class ProgressiveTestStruct(Container):
    A: ProgressiveList[byte]
    B: ProgressiveList[uint64]
    C: ProgressiveList[SmallTestStruct]
    D: ProgressiveList[ProgressiveList[VarTestStruct]]


class BitsStruct(Container):
    A: Bitlist[5]
    B: Bitvector[2]
    C: Bitvector[1]
    D: Bitlist[6]
    E: Bitvector[8]


class ProgressiveBitsStruct(Container):
    A: Bitvector[256]
    B: Bitlist[256]
    C: ProgressiveBitlist
    D: Bitvector[257]
    E: Bitlist[257]
    F: ProgressiveBitlist
    G: Bitvector[1280]
    H: Bitlist[1280]
    I: ProgressiveBitlist
    J: Bitvector[1281]
    K: Bitlist[1281]
    L: ProgressiveBitlist


def container_case_fn(rng: Random, mode: RandomizationMode, typ: type[View], chaos: bool = False):
    return get_random_ssz_object(
        rng, typ, max_bytes_length=2000, max_list_length=1500, mode=mode, chaos=chaos
    )


PRESET_CONTAINERS: dict[str, tuple[type[View], Sequence[int]]] = {
    "SingleFieldTestStruct": (SingleFieldTestStruct, []),
    "SmallTestStruct": (SmallTestStruct, []),
    "FixedTestStruct": (FixedTestStruct, []),
    "VarTestStruct": (VarTestStruct, [2]),
    "ComplexTestStruct": (ComplexTestStruct, [2, 2 + 4 + 1, 2 + 4 + 1 + 4]),
    "ContainerListTestStruct": (ContainerListTestStruct, [2]),
    "ProgressiveTestStruct": (ProgressiveTestStruct, [0, 4, 8, 12]),
    "BitsStruct": (BitsStruct, [0, 4 + 1 + 1, 4 + 1 + 1 + 4]),
    "ProgressiveBitsStruct": (ProgressiveBitsStruct, [32, 36, 73, 77, 241, 245, 410, 414]),
}


def valid_container_cases(rng: Random, name: str, typ: type[View], offsets: Sequence[int]):
    for mode in [RandomizationMode.mode_zero, RandomizationMode.mode_max]:
        yield (
            f"{name}_{mode.to_name()}",
            valid_test_case(lambda rng, mode=mode, typ=typ: container_case_fn(rng, mode, typ), rng),
        )

    if len(offsets) == 0:
        modes = [
            RandomizationMode.mode_random,
            RandomizationMode.mode_zero,
            RandomizationMode.mode_max,
        ]
    else:
        modes = list(RandomizationMode)

    for mode in modes:
        for variation in range(3):
            yield (
                f"{name}_{mode.to_name()}_chaos_{variation}",
                valid_test_case(
                    lambda rng, mode=mode, typ=typ: container_case_fn(rng, mode, typ, chaos=True),
                    rng,
                ),
            )
    # Notes: Below is the second wave of iteration, and only the random mode is selected
    # for container without offset since ``RandomizationMode.mode_zero`` and ``RandomizationMode.mode_max``
    # are deterministic.
    modes = [RandomizationMode.mode_random] if len(offsets) == 0 else list(RandomizationMode)
    for mode in modes:
        for variation in range(10):
            yield (
                f"{name}_{mode.to_name()}_{variation}",
                valid_test_case(
                    lambda rng, mode=mode, typ=typ: container_case_fn(rng, mode, typ), rng
                ),
            )


def empty_list_cases():
    """
    Explicit test cases for containers with selectively empty list fields.
    Catches implementations that incorrectly mix in the list limit
    instead of 0 for the length when computing hash tree roots of empty lists.

    Note: cases where *all* lists are empty are already covered by mode_nil_count
    in valid_container_cases via PRESET_CONTAINERS. These cases target selective
    emptiness (e.g. B empty but D populated) which mode_nil_count cannot produce.
    """
    rng = Random(5678)

    # ComplexTestStruct: empty basic list B, other fields populated
    yield (
        "ComplexTestStruct_empty_list_B",
        valid_test_case(
            lambda rng: ComplexTestStruct(
                A=uint16(0xDEAD),
                B=List[uint16, 128](),
                C=uint8(0x42),
                D=ByteList[256](b"\xab\xcd\xef"),
                E=VarTestStruct(
                    A=uint16(0x5678),
                    B=List[uint16, 1024](uint16(1), uint16(2)),
                    C=uint8(0xFF),
                ),
                F=Vector[FixedTestStruct, 4](
                    *(FixedTestStruct(A=uint8(i), B=uint64(i * 10), C=uint32(i * 100))
                      for i in range(4))
                ),
                G=Vector[VarTestStruct, 2](
                    VarTestStruct(
                        A=uint16(0xAAAA),
                        B=List[uint16, 1024](uint16(100), uint16(200)),
                        C=uint8(0x01),
                    ),
                    VarTestStruct(
                        A=uint16(0xBBBB),
                        B=List[uint16, 1024](uint16(300), uint16(400)),
                        C=uint8(0x02),
                    ),
                ),
            ),
            rng,
        ),
    )

    # ComplexTestStruct: empty byte list D, other fields populated
    yield (
        "ComplexTestStruct_empty_list_D",
        valid_test_case(
            lambda rng: ComplexTestStruct(
                A=uint16(0xBEEF),
                B=List[uint16, 128](uint16(1), uint16(2), uint16(3)),
                C=uint8(0x33),
                D=ByteList[256](b""),
                E=VarTestStruct(
                    A=uint16(0x9999),
                    B=List[uint16, 1024](uint16(7), uint16(8)),
                    C=uint8(0x11),
                ),
                F=Vector[FixedTestStruct, 4](
                    *(FixedTestStruct(A=uint8(i + 10), B=uint64(i * 20), C=uint32(i * 200))
                      for i in range(4))
                ),
                G=Vector[VarTestStruct, 2](
                    VarTestStruct(
                        A=uint16(0xCCCC),
                        B=List[uint16, 1024](uint16(300), uint16(400)),
                        C=uint8(0x03),
                    ),
                    VarTestStruct(
                        A=uint16(0xDDDD),
                        B=List[uint16, 1024](uint16(500)),
                        C=uint8(0x04),
                    ),
                ),
            ),
            rng,
        ),
    )

    # ComplexTestStruct: both list fields B and D empty, nested lists populated
    yield (
        "ComplexTestStruct_empty_lists_BD",
        valid_test_case(
            lambda rng: ComplexTestStruct(
                A=uint16(0xFACE),
                B=List[uint16, 128](),
                C=uint8(0x77),
                D=ByteList[256](b""),
                E=VarTestStruct(
                    A=uint16(0x1111),
                    B=List[uint16, 1024](uint16(42)),
                    C=uint8(0x22),
                ),
                F=Vector[FixedTestStruct, 4](
                    *(FixedTestStruct(A=uint8(i + 20), B=uint64(i * 30), C=uint32(i * 300))
                      for i in range(4))
                ),
                G=Vector[VarTestStruct, 2](
                    VarTestStruct(
                        A=uint16(0xEEEE),
                        B=List[uint16, 1024](uint16(600)),
                        C=uint8(0x05),
                    ),
                    VarTestStruct(
                        A=uint16(0xFFFF),
                        B=List[uint16, 1024](uint16(700), uint16(800)),
                        C=uint8(0x06),
                    ),
                ),
            ),
            rng,
        ),
    )

    # ContainerListTestStruct: non-empty container list with empty inner lists
    yield (
        "ContainerListTestStruct_nested_empty_lists",
        valid_test_case(
            lambda rng: ContainerListTestStruct(
                A=uint16(0x9876),
                B=List[VarTestStruct, 8](
                    VarTestStruct(
                        A=uint16(0x1111),
                        B=List[uint16, 1024](),
                        C=uint8(0xAA),
                    ),
                    VarTestStruct(
                        A=uint16(0x2222),
                        B=List[uint16, 1024](),
                        C=uint8(0xBB),
                    ),
                ),
                C=uint8(0xCC),
            ),
            rng,
        ),
    )


def valid_cases():
    rng = Random(1234)
    for name, (typ, offsets) in PRESET_CONTAINERS.items():
        yield from valid_container_cases(rng, name, typ, offsets)
    yield from empty_list_cases()


def mod_offset(b: bytes, offset_index: int, change: Callable[[int], int]):
    return (
        b[:offset_index]
        + (
            change(int.from_bytes(b[offset_index : offset_index + 4], byteorder="little"))
            & 0xFFFFFFFF
        ).to_bytes(length=4, byteorder="little")
        + b[offset_index + 4 :]
    )


def invalid_container_cases(rng: Random, name: str, typ: type[View], offsets: Sequence[int]):
    # using mode_max_count, so that the extra byte cannot be picked up as normal list content
    yield (
        f"{name}_extra_byte",
        invalid_test_case(
            typ,
            lambda rng, typ=typ: (
                serialize(container_case_fn(rng, RandomizationMode.mode_max_count, typ)) + b"\x00"
            ),
            rng,
        ),
    )

    if len(offsets) != 0:
        # Note: there are many more ways to have invalid offsets,
        # these are just example to get clients started looking into hardening ssz.
        for mode in [
            RandomizationMode.mode_random,
            RandomizationMode.mode_nil_count,
            RandomizationMode.mode_one_count,
            RandomizationMode.mode_max_count,
        ]:
            for offset_index in offsets:
                for description, change in [
                    ("plus_one", lambda x: x + 1),
                    ("zeroed", lambda x: 0),
                    ("minus_one", lambda x: x - 1),
                ]:

                    def the_test(rng, mode=mode, typ=typ, offset_index=offset_index, change=change):
                        serialized = mod_offset(
                            b=serialize(container_case_fn(rng, mode, typ)),
                            offset_index=offset_index,
                            change=change,
                        )
                        try:
                            _ = deserialize(typ, serialized)
                        except Exception:
                            return serialized
                        raise SkippedTest(
                            "The serialized data still parses fine, it's not invalid data"
                        )

                    yield (
                        f"{name}_{mode.to_name()}_offset_{offset_index}_{description}",
                        invalid_test_case(typ, the_test, rng),
                    )
                if mode == RandomizationMode.mode_max_count:

                    def the_test(rng, mode=mode, typ=typ, offset_index=offset_index, change=change):
                        serialized = serialize(container_case_fn(rng, mode, typ))
                        serialized = serialized + serialized[:3]
                        try:
                            _ = deserialize(typ, serialized)
                        except Exception:
                            return serialized
                        raise SkippedTest(
                            "The serialized data still parses fine, it's not invalid data"
                        )

                    yield (
                        f"{name}_{mode.to_name()}_last_offset_{offset_index}_overflow",
                        invalid_test_case(typ, the_test, rng),
                    )
                if mode == RandomizationMode.mode_one_count:

                    def the_test(rng, mode=mode, typ=typ, offset_index=offset_index, change=change):
                        serialized = serialize(container_case_fn(rng, mode, typ))
                        serialized = serialized + serialized[:1]
                        try:
                            _ = deserialize(typ, serialized)
                        except Exception:
                            return serialized
                        raise SkippedTest(
                            "The serialized data still parses fine, it's not invalid data"
                        )

                    yield (
                        f"{name}_{mode.to_name()}_last_offset_{offset_index}_wrong_byte_length",
                        invalid_test_case(typ, the_test, rng),
                    )


def invalid_cases():
    rng = Random(1234)
    for name, (typ, offsets) in PRESET_CONTAINERS.items():
        yield from invalid_container_cases(rng, name, typ, offsets)
