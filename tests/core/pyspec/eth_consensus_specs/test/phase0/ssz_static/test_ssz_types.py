"""Comprehensive unit tests for the SSZ type system (ssz_typing.py).

Tests cover: basic types, parameterized types, containers, vectors, lists,
bitvectors, bitlists, byte arrays, isinstance/issubclass, introspection,
copy semantics, and unions.
"""

import copy as copy_module

import pytest

from eth_consensus_specs.utils.ssz.ssz_typing import (
    BasicView,
    Bitlist,
    Bitvector,
    boolean,
    ByteList,
    ByteVector,
    Bytes1,
    Bytes4,
    Bytes32,
    Bytes48,
    Bytes96,
    Container,
    List,
    Union,
    Vector,
    View,
    byte,
    uint,
    uint8,
    uint16,
    uint32,
    uint64,
    uint128,
    uint256,
)


# ---------------------------------------------------------------------------
# 1. Basic type construction and arithmetic
# ---------------------------------------------------------------------------
class TestBasicTypes:
    def test_uint64_construction(self):
        v = uint64(42)
        assert v == 42
        assert int(v) == 42

    def test_uint64_from_bytes(self):
        data = (99).to_bytes(8, "little")
        v = uint64(data)
        assert v == 99

    def test_uint64_default(self):
        v = uint64()
        assert v == 0

    def test_uint_arithmetic_returns_int(self):
        a = uint64(10)
        b = uint64(3)
        result = a + b
        # Arithmetic on uint returns plain int (not uint64)
        assert result == 13
        assert type(result) is int

    def test_uint_subtraction(self):
        result = uint64(10) - uint64(3)
        assert result == 7
        assert type(result) is int

    def test_uint_multiplication(self):
        result = uint64(5) * uint64(6)
        assert result == 30

    def test_boolean_construction(self):
        t = boolean(True)
        f = boolean(False)
        assert bool(t) is True
        assert bool(f) is False

    def test_boolean_default(self):
        b = boolean()
        assert bool(b) is False

    def test_boolean_from_int(self):
        b = boolean(1)
        assert bool(b) is True
        b0 = boolean(0)
        assert bool(b0) is False

    def test_boolean_equality(self):
        assert boolean(True) == boolean(True)
        assert boolean(True) != boolean(False)
        assert boolean(True) == True  # noqa: E712
        assert boolean(False) == False  # noqa: E712

    def test_boolean_int_conversion(self):
        assert int(boolean(True)) == 1
        assert int(boolean(False)) == 0

    def test_uint8_byte_length(self):
        assert uint8.type_byte_length() == 1

    def test_uint16_byte_length(self):
        assert uint16.type_byte_length() == 2

    def test_uint32_byte_length(self):
        assert uint32.type_byte_length() == 4

    def test_uint64_byte_length(self):
        assert uint64.type_byte_length() == 8

    def test_uint128_byte_length(self):
        assert uint128.type_byte_length() == 16

    def test_uint256_byte_length(self):
        assert uint256.type_byte_length() == 32


# ---------------------------------------------------------------------------
# 2. Parameterized type caching
# ---------------------------------------------------------------------------
class TestTypeCaching:
    def test_list_type_identity(self):
        T1 = List[uint64, 128]
        T2 = List[uint64, 128]
        assert T1 is T2

    def test_vector_type_identity(self):
        T1 = Vector[uint64, 4]
        T2 = Vector[uint64, 4]
        assert T1 is T2

    def test_bitvector_type_identity(self):
        T1 = Bitvector[8]
        T2 = Bitvector[8]
        assert T1 is T2

    def test_bitlist_type_identity(self):
        T1 = Bitlist[128]
        T2 = Bitlist[128]
        assert T1 is T2

    def test_bytevector_type_identity(self):
        T1 = ByteVector[32]
        T2 = ByteVector[32]
        assert T1 is T2

    def test_bytelist_type_identity(self):
        T1 = ByteList[256]
        T2 = ByteList[256]
        assert T1 is T2

    def test_different_params_different_type(self):
        T1 = List[uint64, 128]
        T2 = List[uint64, 256]
        assert T1 is not T2


# ---------------------------------------------------------------------------
# 3. Custom type subclassing
# ---------------------------------------------------------------------------
class TestCustomSubclassing:
    def test_slot_subclass(self):
        class Slot(uint64):
            pass

        s = Slot(42)
        assert s == 42
        assert isinstance(s, uint64)
        assert isinstance(s, uint)
        assert isinstance(s, int)
        assert Slot.type_byte_length() == 8

    def test_custom_bytes_subclass(self):
        class Version(Bytes4):
            pass

        v = Version(b"\x01\x02\x03\x04")
        assert len(v) == 4
        assert isinstance(v, bytes)
        assert isinstance(v, ByteVector)


# ---------------------------------------------------------------------------
# 4. Container
# ---------------------------------------------------------------------------
class TestContainer:
    def test_construction_with_kwargs(self):
        class Point(Container):
            x: uint64
            y: uint64

        p = Point(x=uint64(1), y=uint64(2))
        assert p.x == 1
        assert p.y == 2

    def test_default_construction(self):
        class Point(Container):
            x: uint64
            y: uint64

        p = Point()
        assert p.x == 0
        assert p.y == 0

    def test_field_access(self):
        class Point(Container):
            x: uint64
            y: uint64

        p = Point(x=uint64(10), y=uint64(20))
        assert p.x == 10
        assert p.y == 20

    def test_field_mutation_with_coercion(self):
        class Point(Container):
            x: uint64
            y: uint64

        p = Point(x=uint64(1), y=uint64(2))
        p.x = 99  # plain int should be coerced to uint64
        assert p.x == 99
        assert isinstance(p.x, uint64)

    def test_construction_with_coercion(self):
        class Point(Container):
            x: uint64
            y: uint64

        p = Point(x=10, y=20)  # plain ints coerced
        assert isinstance(p.x, uint64)
        assert isinstance(p.y, uint64)

    def test_equality(self):
        class Point(Container):
            x: uint64
            y: uint64

        p1 = Point(x=uint64(1), y=uint64(2))
        p2 = Point(x=uint64(1), y=uint64(2))
        assert p1 == p2

    def test_inequality(self):
        class Point(Container):
            x: uint64
            y: uint64

        p1 = Point(x=uint64(1), y=uint64(2))
        p2 = Point(x=uint64(1), y=uint64(3))
        assert p1 != p2

    def test_nested_container_default(self):
        class Inner(Container):
            a: uint64

        class Outer(Container):
            inner: Inner
            b: uint32

        o = Outer()
        assert o.b == 0
        assert isinstance(o.inner, Inner)
        assert o.inner.a == 0


# ---------------------------------------------------------------------------
# 5. Vector
# ---------------------------------------------------------------------------
class TestVector:
    def test_construction(self):
        V = Vector[uint64, 3]
        v = V(uint64(1), uint64(2), uint64(3))
        assert len(v) == 3

    def test_construction_from_iterable(self):
        V = Vector[uint64, 3]
        v = V([uint64(1), uint64(2), uint64(3)])
        assert len(v) == 3

    def test_default_construction(self):
        V = Vector[uint64, 3]
        v = V()
        assert len(v) == 3
        assert all(x == 0 for x in v)

    def test_indexing(self):
        V = Vector[uint64, 3]
        v = V(uint64(10), uint64(20), uint64(30))
        assert v[0] == 10
        assert v[1] == 20
        assert v[2] == 30

    def test_iteration(self):
        V = Vector[uint64, 3]
        v = V(uint64(1), uint64(2), uint64(3))
        assert list(v) == [1, 2, 3]

    def test_length(self):
        V = Vector[uint64, 5]
        v = V()
        assert len(v) == 5

    def test_setitem_with_coercion(self):
        V = Vector[uint64, 3]
        v = V()
        v[0] = 42  # plain int should be coerced
        assert v[0] == 42
        assert isinstance(v[0], uint64)

    def test_wrong_length_raises(self):
        V = Vector[uint64, 3]
        with pytest.raises(AssertionError):
            V(uint64(1), uint64(2))

    def test_equality(self):
        V = Vector[uint64, 2]
        v1 = V(uint64(1), uint64(2))
        v2 = V(uint64(1), uint64(2))
        assert v1 == v2

    def test_construction_from_generator(self):
        V = Vector[uint64, 3]
        v = V(uint64(i) for i in range(3))
        assert len(v) == 3
        assert v[0] == 0
        assert v[2] == 2


# ---------------------------------------------------------------------------
# 6. List
# ---------------------------------------------------------------------------
class TestList:
    def test_construction(self):
        L = List[uint64, 128]
        lst = L(uint64(1), uint64(2), uint64(3))
        assert len(lst) == 3

    def test_construction_from_iterable(self):
        L = List[uint64, 128]
        lst = L([uint64(1), uint64(2)])
        assert len(lst) == 2

    def test_append(self):
        L = List[uint64, 128]
        lst = L()
        lst.append(uint64(42))
        assert len(lst) == 1
        assert lst[0] == 42

    def test_append_with_coercion(self):
        L = List[uint64, 128]
        lst = L()
        lst.append(42)  # plain int coerced
        assert isinstance(lst[0], uint64)

    def test_empty_construction(self):
        L = List[uint64, 128]
        lst = L()
        assert len(lst) == 0

    def test_length(self):
        L = List[uint64, 128]
        lst = L(uint64(1), uint64(2), uint64(3))
        assert len(lst) == 3

    def test_iteration(self):
        L = List[uint64, 128]
        lst = L(uint64(10), uint64(20))
        assert list(lst) == [10, 20]

    def test_construction_from_generator(self):
        L = List[uint64, 128]
        lst = L(uint64(i) for i in range(5))
        assert len(lst) == 5


# ---------------------------------------------------------------------------
# 7. Bitvector
# ---------------------------------------------------------------------------
class TestBitvector:
    def test_construction(self):
        BV = Bitvector[8]
        bv = BV(True, False, True, False, True, False, True, False)
        assert len(bv) == 8
        assert bv[0] is True
        assert bv[1] is False

    def test_default_construction(self):
        BV = Bitvector[4]
        bv = BV()
        assert len(bv) == 4
        assert all(b is False for b in bv)

    def test_slicing(self):
        BV = Bitvector[4]
        bv = BV(True, True, False, False)
        assert bv[0:2] == [True, True]

    def test_slice_assignment(self):
        N = 4
        BV = Bitvector[N]
        bv = BV(True, False, True, False)
        bv[1:] = bv[:N - 1]  # shift right
        assert bv[1] is True
        assert bv[2] is False
        assert bv[3] is True

    def test_construction_from_generator(self):
        BV = Bitvector[4]
        bv = BV(bool(i % 2) for i in range(4))
        assert len(bv) == 4


# ---------------------------------------------------------------------------
# 8. Bitlist
# ---------------------------------------------------------------------------
class TestBitlist:
    def test_construction(self):
        BL = Bitlist[128]
        bl = BL(True, False, True)
        assert len(bl) == 3

    def test_empty_construction(self):
        BL = Bitlist[128]
        bl = BL()
        assert len(bl) == 0

    def test_length(self):
        BL = Bitlist[128]
        bl = BL(True, False, True, True)
        assert len(bl) == 4

    def test_append(self):
        BL = Bitlist[128]
        bl = BL()
        bl.append(True)
        bl.append(False)
        assert len(bl) == 2
        assert bl[0] is True
        assert bl[1] is False


# ---------------------------------------------------------------------------
# 9. ByteVector / ByteList
# ---------------------------------------------------------------------------
class TestByteArrays:
    def test_bytevector_construction(self):
        bv = Bytes32(b"\x00" * 32)
        assert len(bv) == 32

    def test_bytevector_default(self):
        bv = Bytes32()
        assert len(bv) == 32
        assert bv == b"\x00" * 32

    def test_bytevector_isinstance_bytes(self):
        bv = Bytes32()
        assert isinstance(bv, bytes)

    def test_bytelist_construction(self):
        BL = ByteList[256]
        bl = BL(b"\x01\x02\x03")
        assert len(bl) == 3

    def test_bytelist_isinstance_bytes(self):
        BL = ByteList[256]
        bl = BL(b"\x01")
        assert isinstance(bl, bytes)

    def test_bytevector_wrong_length_raises(self):
        with pytest.raises(AssertionError):
            Bytes32(b"\x00" * 31)

    def test_bytes1(self):
        b = Bytes1(b"\xff")
        assert len(b) == 1
        assert isinstance(b, bytes)

    def test_bytes4(self):
        b = Bytes4(b"\x01\x02\x03\x04")
        assert len(b) == 4

    def test_bytes48(self):
        b = Bytes48(b"\x00" * 48)
        assert len(b) == 48

    def test_bytes96(self):
        b = Bytes96(b"\x00" * 96)
        assert len(b) == 96

    def test_bytevector_equality_with_bytes(self):
        bv = Bytes4(b"\x01\x02\x03\x04")
        # ByteVector inherits from bytes, so == with bytes should work
        assert bv == b"\x01\x02\x03\x04"

    def test_bytelist_empty(self):
        BL = ByteList[256]
        bl = BL()
        assert len(bl) == 0


# ---------------------------------------------------------------------------
# 10. isinstance / issubclass
# ---------------------------------------------------------------------------
class TestInstanceChecks:
    def test_uint64_isinstance_uint(self):
        assert isinstance(uint64(1), uint)

    def test_uint64_isinstance_basicview(self):
        assert isinstance(uint64(1), BasicView)

    def test_uint64_isinstance_view(self):
        assert isinstance(uint64(1), View)

    def test_uint64_isinstance_int(self):
        assert isinstance(uint64(1), int)

    def test_boolean_isinstance_basicview(self):
        assert isinstance(boolean(True), BasicView)

    def test_container_subclass(self):
        class MyC(Container):
            x: uint64

        assert issubclass(MyC, Container)
        assert issubclass(MyC, View)
        assert isinstance(MyC(), Container)

    def test_bytevector_isinstance(self):
        assert isinstance(Bytes32(), ByteVector)
        assert isinstance(Bytes32(), View)
        assert isinstance(Bytes32(), bytes)

    def test_vector_isinstance(self):
        V = Vector[uint64, 3]
        v = V()
        assert isinstance(v, Vector)
        assert isinstance(v, View)

    def test_list_isinstance(self):
        L = List[uint64, 128]
        lst = L()
        assert isinstance(lst, List)
        assert isinstance(lst, View)

    def test_bitvector_isinstance(self):
        BV = Bitvector[8]
        bv = BV()
        assert isinstance(bv, Bitvector)
        assert isinstance(bv, View)

    def test_bitlist_isinstance(self):
        BL = Bitlist[128]
        bl = BL()
        assert isinstance(bl, Bitlist)
        assert isinstance(bl, View)

    def test_issubclass_parameterized_vector(self):
        V = Vector[uint64, 3]
        assert issubclass(V, Vector)
        assert issubclass(V, View)

    def test_issubclass_parameterized_list(self):
        L = List[uint64, 128]
        assert issubclass(L, List)
        assert issubclass(L, View)

    def test_issubclass_bytevector(self):
        assert issubclass(Bytes32, ByteVector)
        assert issubclass(Bytes32, View)
        assert issubclass(Bytes32, bytes)

    def test_issubclass_uint(self):
        assert issubclass(uint64, uint)
        assert issubclass(uint64, BasicView)
        assert issubclass(uint64, int)

    def test_issubclass_boolean(self):
        assert issubclass(boolean, BasicView)
        assert issubclass(boolean, View)


# ---------------------------------------------------------------------------
# 11. Introspection
# ---------------------------------------------------------------------------
class TestIntrospection:
    def test_container_fields(self):
        class MyC(Container):
            a: uint64
            b: uint32

        fields = MyC.fields()
        assert fields == {"a": uint64, "b": uint32}

    def test_vector_element_cls(self):
        V = Vector[uint64, 4]
        assert V.element_cls() is uint64

    def test_vector_vector_length(self):
        V = Vector[uint64, 4]
        assert V.vector_length() == 4

    def test_list_element_cls(self):
        L = List[uint64, 128]
        assert L.element_cls() is uint64

    def test_list_limit(self):
        L = List[uint64, 128]
        assert L.limit() == 128

    def test_bitvector_vector_length(self):
        BV = Bitvector[16]
        assert BV.vector_length() == 16

    def test_bitlist_limit(self):
        BL = Bitlist[64]
        assert BL.limit() == 64

    def test_bytevector_vector_length(self):
        assert Bytes32.vector_length() == 32

    def test_bytelist_limit(self):
        BL = ByteList[256]
        assert BL.limit() == 256

    def test_uint64_type_byte_length(self):
        assert uint64.type_byte_length() == 8

    def test_uint64_is_fixed_byte_length(self):
        assert uint64.is_fixed_byte_length() is True

    def test_list_is_not_fixed(self):
        L = List[uint64, 128]
        assert L.is_fixed_byte_length() is False

    def test_vector_fixed_byte_length(self):
        V = Vector[uint64, 4]
        assert V.is_fixed_byte_length() is True
        assert V.type_byte_length() == 32  # 4 * 8

    def test_bitvector_type_byte_length(self):
        BV = Bitvector[16]
        assert BV.type_byte_length() == 2

    def test_bytevector_type_byte_length(self):
        assert Bytes32.type_byte_length() == 32

    def test_container_is_fixed(self):
        class Fixed(Container):
            a: uint64
            b: uint32

        assert Fixed.is_fixed_byte_length() is True
        assert Fixed.type_byte_length() == 12

    def test_container_is_variable(self):
        class Variable(Container):
            a: uint64
            b: List[uint64, 128]

        assert Variable.is_fixed_byte_length() is False

    def test_bytevector_element_cls(self):
        assert Bytes32.element_cls() is byte

    def test_bytelist_element_cls(self):
        BL = ByteList[256]
        assert BL.element_cls() is byte


# ---------------------------------------------------------------------------
# 12. Copy
# ---------------------------------------------------------------------------
class TestCopy:
    def test_uint_copy(self):
        v = uint64(42)
        c = v.copy()
        assert c == v
        assert type(c) is uint64

    def test_boolean_copy(self):
        b = boolean(True)
        c = b.copy()
        assert bool(c) is True

    def test_bytevector_copy(self):
        bv = Bytes32(b"\x01" * 32)
        c = bv.copy()
        assert c == bv
        assert c is not bv

    def test_container_deep_copy(self):
        class Inner(Container):
            v: uint64

        class Outer(Container):
            inner: Inner
            x: uint64

        o = Outer(inner=Inner(v=uint64(10)), x=uint64(20))
        c = o.copy()
        c.inner.v = 99
        assert o.inner.v == 10  # original not affected

    def test_vector_deep_copy(self):
        class Elem(Container):
            v: uint64

        V = Vector[Elem, 2]
        v = V(Elem(v=uint64(1)), Elem(v=uint64(2)))
        c = v.copy()
        c[0].v = 99
        assert v[0].v == 1  # original not affected

    def test_list_deep_copy(self):
        class Elem(Container):
            v: uint64

        L = List[Elem, 128]
        lst = L(Elem(v=uint64(1)), Elem(v=uint64(2)))
        c = lst.copy()
        c[0].v = 99
        assert lst[0].v == 1  # original not affected

    def test_bitvector_copy(self):
        BV = Bitvector[4]
        bv = BV(True, False, True, False)
        c = bv.copy()
        c[0] = False
        assert bv[0] is True  # original not affected

    def test_bitlist_copy(self):
        BL = Bitlist[128]
        bl = BL(True, False)
        c = bl.copy()
        c[0] = False
        assert bl[0] is True

    def test_python_copy_module(self):
        class Point(Container):
            x: uint64
            y: uint64

        p = Point(x=uint64(1), y=uint64(2))
        c = copy_module.copy(p)
        c.x = 99
        assert p.x == 1

    def test_python_deepcopy_module(self):
        class Point(Container):
            x: uint64
            y: uint64

        p = Point(x=uint64(1), y=uint64(2))
        c = copy_module.deepcopy(p)
        c.x = 99
        assert p.x == 1


# ---------------------------------------------------------------------------
# 13. Union
# ---------------------------------------------------------------------------
class TestUnion:
    def test_construction(self):
        U = Union[None, uint64]
        u = U(selector=1, value=uint64(42))
        assert u.selector() == 1
        assert u.value() == 42

    def test_none_variant(self):
        U = Union[None, uint64]
        u = U(selector=0, value=None)
        assert u.selector() == 0
        assert u.value() is None

    def test_options(self):
        U = Union[None, uint64, uint32]
        opts = U.options()
        assert len(opts) == 3
        assert opts[0] is None
        assert opts[1] is uint64
        assert opts[2] is uint32

    def test_union_isinstance(self):
        U = Union[None, uint64]
        u = U(selector=0, value=None)
        assert isinstance(u, Union)
        assert isinstance(u, View)

    def test_union_copy(self):
        U = Union[None, uint64]
        u = U(selector=1, value=uint64(42))
        c = u.copy()
        assert c.selector() == 1
        assert c.value() == 42
        assert c is not u

    def test_union_type_caching(self):
        U1 = Union[None, uint64]
        U2 = Union[None, uint64]
        assert U1 is U2

    def test_union_is_variable_size(self):
        U = Union[None, uint64]
        assert U.is_fixed_byte_length() is False
