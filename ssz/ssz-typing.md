# SSZ Type System

This document defines the complete SSZ type system as executable Python. The build
pipeline extracts all Python code blocks and concatenates them into `ssz_typing.py`.

## Base classes

All SSZ values derive from `View`. Basic (fixed-size, non-composite) values also
derive from `BasicView`.

```python
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


class BasicView(View):
    """Base class for basic SSZ types (uintN, boolean)."""

    @classmethod
    def is_fixed_byte_length(cls):
        return True
```

## Unsigned integers

`uint` inherits from both `BasicView` and `int`. Arithmetic on `uint` values
returns plain `int`; coercion happens on assignment into typed containers.

```python
class uint(BasicView, int):
    _byte_length = 0

    def __new__(cls, value=0):
        if isinstance(value, bytes):
            value = int.from_bytes(value, "little")
        return int.__new__(cls, int(value))

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

    def __repr__(self):
        return f"boolean({self._value})"

    @classmethod
    def type_byte_length(cls):
        return 1

    def copy(self):
        return boolean(self._value)


bit = boolean
byte = uint8
```

## Byte arrays

`ByteVector` and `ByteList` inherit from `(View, bytes)` so that
`isinstance(v, bytes)` is `True`.

```python
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
```

## Vector and List

Parameterized composite types. The `__class_getitem__` cache ensures that
`List[uint64, 128] is List[uint64, 128]`.

```python
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

    def __init__(self, *args):
        if len(args) == 0:
            # Default: fill with default values
            self._data = [self._element_type() for _ in range(self._length)]
        elif len(args) == 1 and hasattr(args[0], "__iter__") and not isinstance(args[0], (str, bytes)):
            self._data = list(args[0])
        else:
            self._data = list(args)
        assert len(self._data) == self._length, (
            f"Vector expects {self._length} elements, got {len(self._data)}"
        )

    def __getitem__(self, index):
        if isinstance(index, slice):
            return self._data[index]
        return self._data[index]

    def __setitem__(self, index, value):
        if isinstance(index, slice):
            self._data[index] = value
        else:
            if self._element_type and not isinstance(value, self._element_type):
                value = self._element_type(value)
            self._data[index] = value

    def __len__(self):
        return len(self._data)

    def __iter__(self):
        return iter(self._data)

    def __eq__(self, other):
        if isinstance(other, Vector):
            return self._data == other._data
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

    def __init__(self, *args):
        if len(args) == 0:
            self._data = []
        elif len(args) == 1 and hasattr(args[0], "__iter__") and not isinstance(args[0], (str, bytes)):
            self._data = list(args[0])
        else:
            self._data = list(args)

    def __getitem__(self, index):
        if isinstance(index, slice):
            result = self.__class__(*self._data[index])
            return result
        return self._data[index]

    def __setitem__(self, index, value):
        if isinstance(index, slice):
            self._data[index] = value
        else:
            if self._element_type and not isinstance(value, self._element_type):
                value = self._element_type(value)
            self._data[index] = value

    def __len__(self):
        return len(self._data)

    def __iter__(self):
        return iter(self._data)

    def __eq__(self, other):
        if isinstance(other, List):
            return self._data == other._data
        return NotImplemented

    def __repr__(self):
        return f"{type(self).__name__}({self._data})"

    def append(self, value):
        if self._element_type and not isinstance(value, self._element_type):
            value = self._element_type(value)
        self._data.append(value)

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
```

## Bitvector and Bitlist

Fixed-length and variable-length sequences of bits.

```python
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
        return NotImplemented

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
        return NotImplemented

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
```

## Container

Containers use `__init_subclass__` to collect `__annotations__` and support
a `fields()` classmethod. `__setattr__` coerces raw values to the declared
field type.

```python
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

    def __init__(self, **kwargs):
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
```

## Union

Tagged union with `.selector()` and `.value()` method accessors.

```python
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
```

## Progressive types and CompatibleUnion

Progressive types support forward-compatible schema evolution. `CompatibleUnion`
uses `.selector()` and `.data()` method accessors.

```python
class ProgressiveContainer(View):
    _field_names = ()
    _field_types = ()
    _active_fields = ()

    def __class_getitem__(cls, params):
        # ProgressiveContainer(active_fields=[...]) syntax
        # Not commonly used in class_getitem, but needed for type creation
        return cls

    def __init_subclass__(cls, active_fields=None, **kwargs):
        super().__init_subclass__(**kwargs)
        if active_fields is not None:
            cls._active_fields = tuple(active_fields)
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
```

## Path

Exists only for import compatibility.

```python
class Path:
    """Unused — exists only for import compatibility."""
    pass
```
