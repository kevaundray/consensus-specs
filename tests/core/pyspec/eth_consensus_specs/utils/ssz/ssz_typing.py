class View:
    """Base class for all SSZ values."""

    @classmethod
    def is_fixed_byte_length(cls):
        raise NotImplementedError

    @classmethod
    def type_byte_length(cls):
        raise NotImplementedError

    def copy(self):
        raise NotImplementedError

    def __copy__(self):
        return self.copy()

    def __deepcopy__(self, memo):
        return self.copy()

    def hash_tree_root(self):
        from eth_consensus_specs.utils.ssz.ssz_spec import hash_tree_root as _htr
        return _htr(self)

    def get_backing(self):
        return self.copy()

    def set_backing(self, backing):
        """Restore state from a previously cached backing (copy)."""
        if hasattr(backing, '__dict__'):
            for key, value in backing.__dict__.items():
                self.__dict__[key] = value
        if hasattr(backing, '_data'):
            self._data = backing._data

    def encode_bytes(self):
        from eth_consensus_specs.utils.ssz.ssz_spec import serialize as _ser
        return _ser(self)


class BasicView(View):
    """Base class for basic SSZ types (uintN, boolean)."""

    @classmethod
    def is_fixed_byte_length(cls):
        return True


class uint(BasicView, int):
    _byte_length = 0

    def __new__(cls, value=0):
        if isinstance(value, bytes):
            value = int.from_bytes(value, "little")
        value = int(value)
        if cls._byte_length > 0:
            max_value = 2 ** (cls._byte_length * 8)
            if value < 0 or value >= max_value:
                raise ValueError(
                    f"Value {value} out of range for {cls.__name__} (0 to {max_value - 1})"
                )
        return int.__new__(cls, value)

    @classmethod
    def type_byte_length(cls):
        return cls._byte_length

    def copy(self):
        return self.__class__(int(self))


class uint8(uint):
    _byte_length = 1


class uint16(uint):
    _byte_length = 2


class uint32(uint):
    _byte_length = 4


class uint64(uint):
    _byte_length = 8


class uint128(uint):
    _byte_length = 16


class uint256(uint):
    _byte_length = 32


class boolean(BasicView):
    def __init__(self, value=False):
        self._value = bool(int(value) if isinstance(value, uint) else value)

    def __bool__(self):
        return self._value

    def __int__(self):
        return 1 if self._value else 0

    def __eq__(self, other):
        if isinstance(other, boolean):
            return self._value == other._value
        if isinstance(other, (bool, int)):
            return self._value == bool(other)
        return NotImplemented

    def __hash__(self):
        return hash(self._value)

    def __add__(self, other):
        return int(self) + int(other)

    def __radd__(self, other):
        return int(other) + int(self)

    def __sub__(self, other):
        return int(self) - int(other)

    def __rsub__(self, other):
        return int(other) - int(self)

    def __mul__(self, other):
        return int(self) * int(other)

    def __rmul__(self, other):
        return int(other) * int(self)

    def __repr__(self):
        return f"boolean({self._value})"

    @classmethod
    def type_byte_length(cls):
        return 1

    def copy(self):
        return boolean(self._value)


bit = boolean
byte = uint8


class ByteVector(View, bytes):
    _length = 0
    _type_cache = {}

    def __class_getitem__(cls, n):
        n = int(n)
        key = (cls, n)
        if key not in ByteVector._type_cache:
            ByteVector._type_cache[key] = type(
                f"ByteVector[{n}]", (cls,), {"_length": n}
            )
        return ByteVector._type_cache[key]

    def __new__(cls, data=None):
        if data is None:
            data = b"\x00" * cls._length
        if isinstance(data, int):
            data = b"\x00" * data
        if isinstance(data, str):
            if data.startswith("0x") or data.startswith("0X"):
                data = bytes.fromhex(data[2:])
            else:
                data = bytes.fromhex(data)
        instance = bytes.__new__(cls, data)
        if cls._length > 0:
            assert len(instance) == cls._length, (
                f"ByteVector expected {cls._length} bytes, got {len(instance)}"
            )
        return instance

    @classmethod
    def vector_length(cls):
        return cls._length

    @classmethod
    def type_byte_length(cls):
        return cls._length

    @classmethod
    def is_fixed_byte_length(cls):
        return True

    @classmethod
    def element_cls(cls):
        return byte

    def copy(self):
        return self.__class__(bytes(self))


class ByteList(View, bytes):
    _limit = 0
    _type_cache = {}

    def __class_getitem__(cls, n):
        n = int(n)
        key = (cls, n)
        if key not in ByteList._type_cache:
            ByteList._type_cache[key] = type(
                f"ByteList[{n}]", (cls,), {"_limit": n}
            )
        return ByteList._type_cache[key]

    def __new__(cls, data=b""):
        if isinstance(data, int):
            data = b"\x00" * data
        if isinstance(data, str):
            if data.startswith("0x") or data.startswith("0X"):
                data = bytes.fromhex(data[2:])
            else:
                data = bytes.fromhex(data)
        instance = bytes.__new__(cls, data)
        if cls._limit > 0:
            assert len(instance) <= cls._limit, (
                f"ByteList exceeds limit: {len(instance)} > {cls._limit}"
            )
        return instance

    @classmethod
    def limit(cls):
        return cls._limit

    @classmethod
    def is_fixed_byte_length(cls):
        return False

    @classmethod
    def element_cls(cls):
        return byte

    def copy(self):
        return self.__class__(bytes(self))


Bytes1 = ByteVector[1]
Bytes4 = ByteVector[4]
Bytes8 = ByteVector[8]
Bytes20 = ByteVector[20]
Bytes31 = ByteVector[31]
Bytes32 = ByteVector[32]
Bytes48 = ByteVector[48]
Bytes96 = ByteVector[96]


class Vector(View):
    _element_type = None
    _length = 0
    _type_cache = {}

    def __class_getitem__(cls, params):
        if not isinstance(params, tuple):
            params = (params,)
        elem_type, length = params
        length = int(length)
        key = (cls, id(elem_type), length)
        if key not in Vector._type_cache:
            Vector._type_cache[key] = type(
                f"Vector[{getattr(elem_type, '__name__', str(elem_type))}, {length}]",
                (cls,),
                {"_element_type": elem_type, "_length": length},
            )
        return Vector._type_cache[key]

    def _coerce(self, value):
        if self._element_type and not isinstance(value, self._element_type):
            return self._element_type(value)
        return value

    def __init__(self, *args):
        if len(args) == 0:
            # Default: fill with default values
            self._data = [self._element_type() for _ in range(self._length)]
        elif len(args) == 1 and hasattr(args[0], "__iter__") and not isinstance(args[0], (str, bytes)):
            self._data = [self._coerce(v) for v in args[0]]
        else:
            self._data = [self._coerce(v) for v in args]
        assert len(self._data) == self._length, (
            f"Vector expects {self._length} elements, got {len(self._data)}"
        )

    def __getitem__(self, index):
        if isinstance(index, slice):
            return self._data[index]
        return self._data[index]

    def __setitem__(self, index, value):
        if isinstance(index, slice):
            self._data[index] = [self._coerce(v) for v in value]
        else:
            self._data[index] = self._coerce(value)

    def __len__(self):
        return len(self._data)

    def __iter__(self):
        return iter(self._data)

    def __eq__(self, other):
        if isinstance(other, Vector):
            return self._data == other._data
        if isinstance(other, (list, tuple)):
            return self._data == list(other)
        return NotImplemented

    def __hash__(self):
        return hash(tuple(self._data))

    def __repr__(self):
        return f"{type(self).__name__}({self._data})"

    @classmethod
    def element_cls(cls):
        return cls._element_type

    @classmethod
    def vector_length(cls):
        return cls._length

    @classmethod
    def type_byte_length(cls):
        if cls._element_type.is_fixed_byte_length():
            return cls._length * cls._element_type.type_byte_length()
        raise TypeError("Variable-size Vector has no fixed byte length")

    @classmethod
    def is_fixed_byte_length(cls):
        return cls._element_type.is_fixed_byte_length()

    def copy(self):
        return self.__class__(
            elem.copy() if hasattr(elem, "copy") and callable(elem.copy) else elem
            for elem in self._data
        )


class List(View):
    _element_type = None
    _limit = 0
    _type_cache = {}

    def __class_getitem__(cls, params):
        if not isinstance(params, tuple):
            params = (params,)
        elem_type, limit = params
        limit = int(limit)
        key = (cls, id(elem_type), limit)
        if key not in List._type_cache:
            List._type_cache[key] = type(
                f"List[{getattr(elem_type, '__name__', str(elem_type))}, {limit}]",
                (cls,),
                {"_element_type": elem_type, "_limit": limit},
            )
        return List._type_cache[key]

    def _coerce(self, value):
        if self._element_type and not isinstance(value, self._element_type):
            return self._element_type(value)
        return value

    def __init__(self, *args):
        if len(args) == 0:
            self._data = []
        elif len(args) == 1 and hasattr(args[0], "__iter__") and not isinstance(args[0], (str, bytes)):
            self._data = [self._coerce(v) for v in args[0]]
        else:
            self._data = [self._coerce(v) for v in args]

    def __getitem__(self, index):
        if isinstance(index, slice):
            result = self.__class__(*self._data[index])
            return result
        return self._data[index]

    def __setitem__(self, index, value):
        if isinstance(index, slice):
            self._data[index] = [self._coerce(v) for v in value]
        else:
            self._data[index] = self._coerce(value)

    def __len__(self):
        return len(self._data)

    def __iter__(self):
        return iter(self._data)

    def __eq__(self, other):
        if isinstance(other, List):
            return self._data == other._data
        if isinstance(other, (list, tuple)):
            return self._data == list(other)
        return NotImplemented

    def __repr__(self):
        return f"{type(self).__name__}({self._data})"

    def __add__(self, other):
        if isinstance(other, (List, list)):
            return self.__class__(list(self._data) + list(other))
        return NotImplemented

    def __radd__(self, other):
        if isinstance(other, (List, list)):
            return self.__class__(list(other) + list(self._data))
        return NotImplemented

    def append(self, value):
        self._data.append(self._coerce(value))

    def count(self, value):
        return self._data.count(value)

    def index(self, value, *args):
        return self._data.index(value, *args)

    def pop(self, *args):
        return self._data.pop(*args)

    def extend(self, values):
        self._data.extend(self._coerce(v) for v in values)

    @classmethod
    def element_cls(cls):
        return cls._element_type

    @classmethod
    def limit(cls):
        return cls._limit

    @classmethod
    def is_fixed_byte_length(cls):
        return False

    def copy(self):
        return self.__class__(
            elem.copy() if hasattr(elem, "copy") and callable(elem.copy) else elem
            for elem in self._data
        )


class Bitvector(View):
    _length = 0
    _type_cache = {}

    def __class_getitem__(cls, n):
        n = int(n)
        key = (cls, n)
        if key not in Bitvector._type_cache:
            Bitvector._type_cache[key] = type(
                f"Bitvector[{n}]", (cls,), {"_length": n}
            )
        return Bitvector._type_cache[key]

    def __init__(self, *args):
        if len(args) == 0:
            self._data = [False] * self._length
        elif len(args) == 1 and hasattr(args[0], "__iter__") and not isinstance(args[0], (str, bytes)):
            self._data = [bool(b) for b in args[0]]
        else:
            self._data = [bool(b) for b in args]
        assert len(self._data) == self._length, (
            f"Bitvector expects {self._length} bits, got {len(self._data)}"
        )

    def __getitem__(self, index):
        if isinstance(index, slice):
            return self._data[index]
        return self._data[index]

    def __setitem__(self, index, value):
        if isinstance(index, slice):
            self._data[index] = [bool(v) for v in value] if hasattr(value, "__iter__") else value
        else:
            self._data[index] = bool(value)

    def __len__(self):
        return len(self._data)

    def __iter__(self):
        return iter(self._data)

    def __eq__(self, other):
        if isinstance(other, Bitvector):
            return self._data == other._data
        if isinstance(other, (list, tuple)):
            return self._data == list(other)
        return NotImplemented

    def count(self, value):
        return self._data.count(value)

    @classmethod
    def vector_length(cls):
        return cls._length

    @classmethod
    def type_byte_length(cls):
        return (cls._length + 7) // 8

    @classmethod
    def is_fixed_byte_length(cls):
        return True

    def copy(self):
        return self.__class__(list(self._data))


class Bitlist(View):
    _limit = 0
    _type_cache = {}

    def __class_getitem__(cls, n):
        n = int(n)
        key = (cls, n)
        if key not in Bitlist._type_cache:
            Bitlist._type_cache[key] = type(
                f"Bitlist[{n}]", (cls,), {"_limit": n}
            )
        return Bitlist._type_cache[key]

    def __init__(self, *args):
        if len(args) == 0:
            self._data = []
        elif len(args) == 1 and hasattr(args[0], "__iter__") and not isinstance(args[0], (str, bytes)):
            self._data = [bool(b) for b in args[0]]
        else:
            self._data = [bool(b) for b in args]

    def __getitem__(self, index):
        if isinstance(index, slice):
            return self._data[index]
        return self._data[index]

    def __setitem__(self, index, value):
        if isinstance(index, slice):
            self._data[index] = [bool(v) for v in value] if hasattr(value, "__iter__") else value
        else:
            self._data[index] = bool(value)

    def __len__(self):
        return len(self._data)

    def __iter__(self):
        return iter(self._data)

    def __eq__(self, other):
        if isinstance(other, Bitlist):
            return self._data == other._data
        if isinstance(other, (list, tuple)):
            return self._data == list(other)
        return NotImplemented

    def count(self, value):
        return self._data.count(value)

    def append(self, value):
        self._data.append(bool(value))

    @classmethod
    def limit(cls):
        return cls._limit

    @classmethod
    def is_fixed_byte_length(cls):
        return False

    def copy(self):
        return self.__class__(list(self._data))


class Container(View):
    _field_names = ()
    _field_types = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Collect field annotations from this class (not parents)
        annotations = {}
        for name, typ in getattr(cls, "__annotations__", {}).items():
            if not name.startswith("_"):
                annotations[name] = typ
        if annotations:
            cls._field_names = tuple(annotations.keys())
            cls._field_types = tuple(annotations.values())

    def __init__(self, *, backing=None, **kwargs):
        if backing is not None:
            # Copy from a backing object (used by test caching)
            for name in self._field_names:
                val = getattr(backing, name)
                if hasattr(val, "copy") and callable(val.copy):
                    val = val.copy()
                self.__dict__[name] = val
            return
        for name, typ in zip(self._field_names, self._field_types):
            value = kwargs.get(name)
            if value is None:
                # Default value for the type
                value = typ()
            elif not isinstance(value, typ):
                value = typ(value)
            self.__dict__[name] = value

    def __setattr__(self, name, value):
        if name in self._field_names:
            idx = self._field_names.index(name)
            typ = self._field_types[idx]
            if not isinstance(value, typ):
                value = typ(value)
        self.__dict__[name] = value

    def __eq__(self, other):
        if type(self) != type(other):
            return NotImplemented
        return all(
            getattr(self, n) == getattr(other, n) for n in self._field_names
        )

    def __hash__(self):
        return hash(tuple(getattr(self, n) for n in self._field_names))

    def __repr__(self):
        fields = ", ".join(
            f"{n}={getattr(self, n)!r}" for n in self._field_names
        )
        return f"{type(self).__name__}({fields})"

    @classmethod
    def fields(cls):
        return dict(zip(cls._field_names, cls._field_types))

    @classmethod
    def is_fixed_byte_length(cls):
        return all(ft.is_fixed_byte_length() for ft in cls._field_types)

    @classmethod
    def type_byte_length(cls):
        if not cls.is_fixed_byte_length():
            raise TypeError("Variable-size container has no fixed byte length")
        return sum(ft.type_byte_length() for ft in cls._field_types)

    def copy(self):
        return self.__class__(
            **{
                name: getattr(self, name).copy()
                if hasattr(getattr(self, name), "copy")
                and callable(getattr(self, name).copy)
                else getattr(self, name)
                for name in self._field_names
            }
        )


class Union(View):
    _options = ()
    _type_cache = {}

    def __class_getitem__(cls, params):
        if not isinstance(params, tuple):
            params = (params,)
        key = (cls,) + params
        if key not in Union._type_cache:
            Union._type_cache[key] = type(
                f"Union[{', '.join(str(t) for t in params)}]",
                (cls,),
                {"_options": params},
            )
        return Union._type_cache[key]

    def __init__(self, selector=0, value=None):
        self._selector = selector
        self._inner_value = value

    def selector(self):
        return self._selector

    def value(self):
        return self._inner_value

    @classmethod
    def options(cls):
        return list(cls._options)

    @classmethod
    def is_fixed_byte_length(cls):
        return False

    def copy(self):
        inner = self._inner_value
        if inner is not None and hasattr(inner, "copy") and callable(inner.copy):
            inner = inner.copy()
        return self.__class__(selector=self._selector, value=inner)


class _ProgressiveContainerMeta(type):
    """Metaclass that makes ProgressiveContainer(active_fields=[...]) return a base class."""

    _factory_cache = {}

    def __call__(cls, *args, **kwargs):
        # When called as ProgressiveContainer(active_fields=[...]) — class factory
        if cls is ProgressiveContainer and "active_fields" in kwargs and len(args) == 0:
            af = tuple(kwargs["active_fields"])
            key = (cls, af)
            if key not in _ProgressiveContainerMeta._factory_cache:
                _ProgressiveContainerMeta._factory_cache[key] = type.__call__(
                    type,
                    f"ProgressiveContainer(active_fields={list(af)})",
                    (ProgressiveContainer,),
                    {"_active_fields": af},
                )
            return _ProgressiveContainerMeta._factory_cache[key]
        # Normal instance creation for subclasses
        return super().__call__(*args, **kwargs)


class ProgressiveContainer(View, metaclass=_ProgressiveContainerMeta):
    _field_names = ()
    _field_types = ()
    _active_fields = ()

    def __class_getitem__(cls, params):
        return cls

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        annotations = {}
        for name, typ in getattr(cls, "__annotations__", {}).items():
            if not name.startswith("_"):
                annotations[name] = typ
        if annotations:
            cls._field_names = tuple(annotations.keys())
            cls._field_types = tuple(annotations.values())

    def __init__(self, **kwargs):
        for name, typ in zip(self._field_names, self._field_types):
            value = kwargs.get(name)
            if value is None:
                value = typ()
            elif not isinstance(value, typ):
                value = typ(value)
            self.__dict__[name] = value

    def __setattr__(self, name, value):
        if name in self._field_names:
            idx = self._field_names.index(name)
            typ = self._field_types[idx]
            if not isinstance(value, typ):
                value = typ(value)
        self.__dict__[name] = value

    def __eq__(self, other):
        if type(self) != type(other):
            return NotImplemented
        return all(getattr(self, n) == getattr(other, n) for n in self._field_names)

    @classmethod
    def fields(cls):
        return dict(zip(cls._field_names, cls._field_types))

    @classmethod
    def is_fixed_byte_length(cls):
        return False

    def copy(self):
        return self.__class__(
            **{
                name: getattr(self, name).copy()
                if hasattr(getattr(self, name), "copy")
                and callable(getattr(self, name).copy)
                else getattr(self, name)
                for name in self._field_names
            }
        )


class ProgressiveList(View):
    _element_type = None
    _type_cache = {}

    def __class_getitem__(cls, elem_type):
        key = (cls, id(elem_type))
        if key not in ProgressiveList._type_cache:
            ProgressiveList._type_cache[key] = type(
                f"ProgressiveList[{getattr(elem_type, '__name__', str(elem_type))}]",
                (cls,),
                {"_element_type": elem_type},
            )
        return ProgressiveList._type_cache[key]

    def __init__(self, *args):
        if len(args) == 0:
            self._data = []
        elif len(args) == 1 and hasattr(args[0], "__iter__") and not isinstance(args[0], (str, bytes)):
            self._data = list(args[0])
        else:
            self._data = list(args)

    def __getitem__(self, index):
        return self._data[index]

    def __setitem__(self, index, value):
        self._data[index] = value

    def __len__(self):
        return len(self._data)

    def __iter__(self):
        return iter(self._data)

    def append(self, value):
        self._data.append(value)

    @classmethod
    def element_cls(cls):
        return cls._element_type

    @classmethod
    def is_fixed_byte_length(cls):
        return False

    def copy(self):
        return self.__class__(
            elem.copy() if hasattr(elem, "copy") and callable(elem.copy) else elem
            for elem in self._data
        )


class ProgressiveBitlist(View):
    def __init__(self, *args):
        if len(args) == 0:
            self._data = []
        elif len(args) == 1 and hasattr(args[0], "__iter__") and not isinstance(args[0], (str, bytes)):
            self._data = [bool(b) for b in args[0]]
        else:
            self._data = [bool(b) for b in args]

    def __getitem__(self, index):
        return self._data[index]

    def __setitem__(self, index, value):
        self._data[index] = bool(value)

    def __len__(self):
        return len(self._data)

    def __iter__(self):
        return iter(self._data)

    def append(self, value):
        self._data.append(bool(value))

    @classmethod
    def is_fixed_byte_length(cls):
        return False

    def copy(self):
        return self.__class__(list(self._data))


class CompatibleUnion(View):
    _options = {}
    _type_cache = {}

    def __class_getitem__(cls, params):
        if isinstance(params, dict):
            key = (cls,) + tuple(sorted(params.items()))
            if key not in CompatibleUnion._type_cache:
                CompatibleUnion._type_cache[key] = type(
                    f"CompatibleUnion({params})",
                    (cls,),
                    {"_options": params},
                )
            return CompatibleUnion._type_cache[key]
        return cls

    def __init__(self, selector=0, data=None):
        self._selector = selector
        self._data = data

    def selector(self):
        return self._selector

    def data(self):
        return self._data

    @classmethod
    def options(cls):
        return dict(cls._options)

    @classmethod
    def is_fixed_byte_length(cls):
        return False

    def copy(self):
        data = self._data
        if data is not None and hasattr(data, "copy") and callable(data.copy):
            data = data.copy()
        return self.__class__(selector=self._selector, data=data)


def _get_depth(elem_count):
    """Return the Merkle tree depth for the given number of elements."""
    if elem_count <= 1:
        return 0
    return (elem_count - 1).bit_length()


def _next_pow_of_two(i):
    if i <= 1:
        return 1
    return 1 << (i - 1).bit_length()


def _to_gindex(index, depth):
    anchor = 1 << depth
    return anchor | index


def _concat_gindices(gindices):
    out = 1
    for g in gindices:
        bit_len = g.bit_length() - 1
        out <<= bit_len
        out |= g ^ (1 << bit_len)
    return out


class Path:
    """Navigate SSZ type trees and compute generalized indices."""

    def __init__(self, anchor, path=None):
        self._anchor = anchor
        self._path = path if path is not None else []

    def __truediv__(self, other):
        if isinstance(other, Path):
            return Path(self._anchor, self._path + other._path)
        last_type = self._anchor if not self._path else self._path[-1][1]
        next_type = _path_navigate_type(last_type, other)
        return Path(self._anchor, self._path + [(other, next_type)])

    def gindex(self):
        if not self._path:
            return 1
        gindices = []
        current_type = self._anchor
        for key, _ in self._path:
            g = _path_key_to_gindex(current_type, key)
            gindices.append(g)
            current_type = _path_navigate_type(current_type, key)
        return _concat_gindices(gindices)

    def navigate_type(self):
        if not self._path:
            return self._anchor
        return self._path[-1][1]


def _path_navigate_type(typ, key):
    """Given a type and a key, return the type of the child."""
    if issubclass(typ, (Container, ProgressiveContainer)):
        return typ.fields()[key]
    if issubclass(typ, (Vector, List)):
        return typ.element_cls()
    if issubclass(typ, (ByteVector, ByteList)):
        return byte
    raise TypeError(f"Cannot navigate type {typ} with key {key}")


def _path_key_to_gindex(typ, key):
    """Given a type and a key, return the generalized index for that child."""
    if issubclass(typ, (Container, ProgressiveContainer)):
        field_names = list(typ.fields().keys())
        field_index = field_names.index(key)
        depth = _get_depth(len(field_names))
        return _to_gindex(field_index, depth)
    if issubclass(typ, List):
        # List has content at gindex 2 (left) and length at gindex 3 (right).
        # Elements within the content subtree are at depth = log2(next_pow_2(chunk_count)).
        elem_type = typ.element_cls()
        limit = typ.limit()
        if issubclass(elem_type, BasicView):
            elems_per_chunk = 32 // elem_type.type_byte_length()
            chunk_i = key // elems_per_chunk
            max_chunks = (limit * elem_type.type_byte_length() + 31) // 32
        else:
            chunk_i = key
            max_chunks = limit
        depth = _get_depth(_next_pow_of_two(max_chunks))
        element_gindex = _to_gindex(chunk_i, depth)
        # Combine with content gindex (2 = left child of list root)
        return _concat_gindices([2, element_gindex])
    if issubclass(typ, Vector):
        elem_type = typ.element_cls()
        length = typ.vector_length()
        if issubclass(elem_type, BasicView):
            elems_per_chunk = 32 // elem_type.type_byte_length()
            chunk_i = key // elems_per_chunk
            max_chunks = (length * elem_type.type_byte_length() + 31) // 32
        else:
            chunk_i = key
            max_chunks = length
        depth = _get_depth(_next_pow_of_two(max_chunks))
        return _to_gindex(chunk_i, depth)
    raise TypeError(f"Cannot compute gindex for type {typ} with key {key}")
