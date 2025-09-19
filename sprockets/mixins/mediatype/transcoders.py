"""
Bundled media type transcoders.

- :class:`.JSONTranscoder` implements JSON encoding/decoding
- :class:`.MsgPackTranscoder` implements msgpack encoding/decoding
- :class:`.FormUrlEncodedTranscoder` implements the venerable form encoding

"""

from __future__ import annotations

import base64
import collections.abc
import dataclasses
import decimal
import json
import pathlib
import string
import typing
import urllib.parse
import uuid

try:
    import pydantic
except ImportError:  # pragma: no cover
    pydantic = None  # type: ignore
try:
    import umsgpack
except ImportError:  # pragma: no cover
    umsgpack = None  # type: ignore

from sprockets.mixins.mediatype import handlers, type_info

_FORM_URLENCODING = {c: '%{:02X}'.format(c) for c in range(255)}
_FORM_URLENCODING.update({ord(c): c for c in string.ascii_letters})
_FORM_URLENCODING.update({ord(c): c for c in string.digits})
_FORM_URLENCODING.update({ord(c): c for c in '*-_.'})

_FORM_URLENCODING_PLUS = _FORM_URLENCODING.copy()
_FORM_URLENCODING_PLUS[ord(' ')] = '+'


def _coerce_value(  # noqa: PLR0911
    obj: type_info.Serializable,
) -> str | bytes | float | None | dict[str, object]:
    """Common value coercion used for JSON & MsgPack.

    Converts special types to their serializable representations:
    - uuid.UUID -> str
    - bytearray -> bytes
    - memoryview -> bytes
    - IsDataclass -> dict
    - DefinesIsoFormat -> str (ISO format)
    - decimal.Decimal -> float
    - pathlib.Path -> str

    Returns None if the object type is not handled by this function.
    """
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, bytearray):
        return bytes(obj)
    if isinstance(obj, memoryview):
        return obj.tobytes()
    if isinstance(obj, type_info.DefinesIsoFormat):
        return obj.isoformat()
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    if isinstance(obj, decimal.Decimal):
        return float(obj)
    if isinstance(obj, pathlib.Path):
        return str(obj)
    return None


class JSONTranscoder(handlers.TextContentHandler):
    """
    JSON transcoder instance.

    :param content_type: the content type that this encoder instance
        implements. If omitted, ``application/json`` is used. This is
        passed directly to the ``TextContentHandler`` initializer.
    :param default_encoding: the encoding to use if none is specified.
        If omitted, this defaults to ``utf-8``. This is passed directly to
        the ``TextContentHandler`` initializer.

    This JSON encoder uses :func:`json.loads` and :func:`json.dumps` to
    implement JSON encoding/decoding.  The :meth:`dump_object` method is
    configured to handle types that the standard JSON module does not
    support.

    .. attribute:: dump_options

       Keyword parameters that are passed to :func:`json.dumps` when
       :meth:`.dumps` is called.  By default, the :meth:`dump_object`
       method is enabled as the default object hook.

    .. attribute:: load_options

       Keyword parameters that are passed to :func:`json.loads` when
       :meth:`.loads` is called.

    """

    dump_options: typing.Dict[str, typing.Any]
    load_options: typing.Dict[str, typing.Any]

    def __init__(
        self,
        content_type: str = 'application/json',
        default_encoding: str = 'utf-8',
    ) -> None:
        super().__init__(
            content_type, self.dumps, self.loads, default_encoding
        )
        self.dump_options = {
            'default': self.dump_object,
            'separators': (',', ':'),
        }
        self.load_options = {}

    def dumps(self, obj: type_info.Serializable) -> str:
        """Dump a :class:`object` instance into a JSON :class:`str`"""
        return json.dumps(obj, **self.dump_options)

    def loads(self, str_repr: str) -> type_info.Deserialized:
        """Transform :class:`str` into an :class:`object` instance."""
        return typing.cast(
            'type_info.Deserialized', json.loads(str_repr, **self.load_options)
        )

    def dump_object(
        self, obj: type_info.Serializable
    ) -> str | dict[str, object] | float:
        """
        Called to encode unrecognized object.

        :param obj: the object to encode
        :return: the encoded object
        :raises TypeError: when `obj` cannot be encoded

        This method is passed as the ``default`` keyword parameter
        to :func:`json.dumps`.  It provides default representations for
        a number of Python language/standard library types.

        +-----------------------------+---------------------------------------+
        | Python Type                 | String Format                         |
        +-----------------------------+---------------------------------------+
        | :class:`bytes`,             | Base64 encoded string.                |
        | :class:`bytearray`,         |                                       |
        | :class:`memoryview`         |                                       |
        +-----------------------------+---------------------------------------+
        : Dataclasses                 | :func:`dataclasses.asdict`            |
        +-----------------------------+---------------------------------------+
        | :class:`datetime.datetime`  | ISO8601 formatted timestamp in the    |
        |                             | extended format including separators, |
        |                             | milliseconds, and the timezone        |
        |                             | designator.                           |
        +-----------------------------+---------------------------------------+
        | :class:`decimal.Decimal`    | Same as ``float(value)``              |
        +-----------------------------+---------------------------------------+
        | :class:`pathlib.Path`       | Same as ``str(value)``                |
        +-----------------------------+---------------------------------------+
        | :class:`pydantic.BaseModel` | `value.model_dump(mode='python')``    |
        +-----------------------------+---------------------------------------+
        | :class:`uuid.UUID`          | Same as ``str(value)``                |
        +-----------------------------+---------------------------------------+

        """
        if (result := _coerce_value(obj)) is not None:
            if isinstance(result, bytes):
                return base64.b64encode(result).decode('ASCII')
            return result
        if pydantic is not None and isinstance(obj, pydantic.BaseModel):
            return obj.model_dump(mode='python')
        raise TypeError('{!r} is not JSON serializable'.format(obj))


class MsgPackTranscoder(handlers.BinaryContentHandler):
    """
    Msgpack Transcoder instance.

    :param content_type: the content type that this encoder instance
        implements. If omitted, ``application/msgpack`` is used. This
        is passed directly to the ``BinaryContentHandler`` initializer.

    This transcoder uses the `umsgpack`_ library to encode and decode
    objects according to the `msgpack format`_.

    .. _umsgpack: https://github.com/vsergeev/u-msgpack-python
    .. _msgpack format: http://msgpack.org/index.html

    """

    PACKABLE_TYPES = (bool, int, float, type(None))

    def __init__(self, content_type: str = 'application/msgpack') -> None:
        if umsgpack is None:
            raise RuntimeError(
                'Cannot import MsgPackTranscoder, umsgpack is not available'
            )

        super().__init__(content_type, self.packb, self.unpackb)

    def packb(self, data: type_info.Serializable) -> bytes:
        """Pack `data` into a :class:`bytes` instance."""
        return umsgpack.packb(self.normalize_datum(data))

    def unpackb(self, data: bytes) -> type_info.Deserialized:
        """Unpack a :class:`object` from a :class:`bytes` instance."""
        return umsgpack.unpackb(data)

    def normalize_datum(
        self, datum: type_info.Serializable
    ) -> type_info.MsgPackable:
        """
        Convert `datum` into something that umsgpack likes.

        :param datum: something that we want to process with umsgpack
        :return: a packable version of `datum`
        :raises TypeError: if `datum` cannot be packed

        This message is called by :meth:`.packb` to recursively normalize
        an input value before passing it to :func:`umsgpack.packb`.  Values
        are normalized according to the following table.

        +-----------------------------------+-------------------------------+
        | **Value**                         | **MsgPack Family**            |
        +-----------------------------------+-------------------------------+
        | :data:`None`                      | `nil byte`_ (0xC0)            |
        +-----------------------------------+-------------------------------+
        | :data:`True`                      | `true byte`_ (0xC3)           |
        +-----------------------------------+-------------------------------+
        | :data:`False`                     | `false byte`_ (0xC2)          |
        +-----------------------------------+-------------------------------+
        | :class:`int`                      | `integer family`_             |
        +-----------------------------------+-------------------------------+
        | :class:`float`                    | `float family`_               |
        +-----------------------------------+-------------------------------+
        | String                            | `str family`_                 |
        +-----------------------------------+-------------------------------+
        | :class:`bytes`                    | `bin family`_                 |
        +-----------------------------------+-------------------------------+
        | :class:`bytearray`                | `bin family`_                 |
        +-----------------------------------+-------------------------------+
        | :class:`memoryview`               | `bin family`_                 |
        +-----------------------------------+-------------------------------+
        | :class:`collections.abc.Sequence` | `array family`_               |
        +-----------------------------------+-------------------------------+
        | :class:`collections.abc.Set`      | `array family`_               |
        +-----------------------------------+-------------------------------+
        | :class:`collections.abc.Mapping`  | `map family`_                 |
        +-----------------------------------+-------------------------------+
        | :class:`uuid.UUID`                | Converted to String           |
        +-----------------------------------+-------------------------------+
        | :class:`datetime.datetime`        | Converted to String           |
        +-----------------------------------+-------------------------------+
        | :class:`decimal.Decimal`          | `float family`_               |
        +-----------------------------------+-------------------------------+
        | :class:`pathlib.Path`             | Converted to String           |
        +-----------------------------------+-------------------------------+
        | :class:`pydantic.BaseModel`       | Recursively encoded after     |
        |                                   | calling ``model_dump()`` in   |
        |                                   | "python" mode.                |
        +-----------------------------------+-------------------------------+

        .. _nil byte: https://github.com/msgpack/msgpack/blob/
           0b8f5ac67cdd130f4d4d4fe6afb839b989fdb86a/spec.md#formats-nil
        .. _true byte: https://github.com/msgpack/msgpack/blob/
           0b8f5ac67cdd130f4d4d4fe6afb839b989fdb86a/spec.md#bool-format-family
        .. _false byte: https://github.com/msgpack/msgpack/blob/
           0b8f5ac67cdd130f4d4d4fe6afb839b989fdb86a/spec.md#bool-format-family
        .. _integer family: https://github.com/msgpack/msgpack/blob/
           0b8f5ac67cdd130f4d4d4fe6afb839b989fdb86a/spec.md#int-format-family
        .. _float family: https://github.com/msgpack/msgpack/blob/
           0b8f5ac67cdd130f4d4d4fe6afb839b989fdb86a/spec.md#float-format-family
        .. _str family: https://github.com/msgpack/msgpack/blob/
           0b8f5ac67cdd130f4d4d4fe6afb839b989fdb86a/spec.md#str-format-family
        .. _array family: https://github.com/msgpack/msgpack/blob/
           0b8f5ac67cdd130f4d4d4fe6afb839b989fdb86a/spec.md#array-format-family
        .. _map family: https://github.com/msgpack/msgpack/blob/
           0b8f5ac67cdd130f4d4d4fe6afb839b989fdb86a/spec.md
           #mapping-format-family
        .. _bin family: https://github.com/msgpack/msgpack/blob/
           0b8f5ac67cdd130f4d4d4fe6afb839b989fdb86a/spec.md#bin-format-family

        """
        if isinstance(datum, self.PACKABLE_TYPES):
            return datum

        if (result := _coerce_value(datum)) is not None:
            if isinstance(result, self.PACKABLE_TYPES):
                return result
            datum = result

        if isinstance(datum, (bytes, str)):
            return datum

        if pydantic is not None and isinstance(datum, pydantic.BaseModel):
            return self.normalize_datum(datum.model_dump(mode='python'))

        if isinstance(datum, (collections.abc.Sequence, collections.abc.Set)):
            return [self.normalize_datum(item) for item in datum]  # type: ignore[arg-type]

        if isinstance(datum, collections.abc.Mapping):
            out = {}
            for k, v in datum.items():
                out[k] = self.normalize_datum(v)  # type: ignore[arg-type]
            return out

        raise TypeError(
            '{} is not msgpackable'.format(datum.__class__.__name__)
        )


@dataclasses.dataclass
class FormUrlEncodingOptions:
    """Configuration knobs for :class:`.FormUrlEncodedTranscoder`"""

    encoding: str = 'utf-8'
    """Encoding use when generating the byte stream from character data."""

    encode_sequences: bool = False
    """Encode sequence values as multiple name=value instances."""

    literal_mapping: dict[typing.Literal[None, True, False], str] = (
        dataclasses.field(
            default_factory=lambda: {None: '', True: 'true', False: 'false'}
        )
    )
    """Mapping from supported literal values to strings."""

    space_as_plus: bool = False
    """Quote spaces as ``%20`` or ``+``."""


class FormUrlEncodedTranscoder:
    """Opinionated transcoder for the venerable x-www-formurlencoded.

    :param encoding_options: keyword parameters are used to initialize
        :class:`FormUrlEncodingOptions`

    This transcoder implements transcoding according to the current
    W3C documentation.  The encoding interface takes mappings or
    sequences of pairs and encodes both the name and value.  The
    following table describes how each supported type is encoded.

    +-----------------------------+----------------------------------------+
    | Value / Type                | Encoding                               |
    +=============================+========================================+
    | character strings           | UTF-8 codepoints before percent-       |
    |                             | encoding the resulting bytes           |
    +-----------------------------+----------------------------------------+
    | space character             | ``%20`` or ``+``                       |
    +-----------------------------+----------------------------------------+
    | :data:`False`               | ``false``                              |
    +-----------------------------+----------------------------------------+
    | :data:`True`                | ``true``                               |
    +-----------------------------+----------------------------------------+
    | :data:`None`                | the empty string                       |
    +-----------------------------+----------------------------------------+
    | numbers including           | ``str(n)``                             |
    | :class:`decimal.Decimal`    |                                        |
    +-----------------------------+----------------------------------------+
    | byte sequences              | percent-encoded bytes                  |
    +-----------------------------+----------------------------------------+
    | :class:`uuid.UUID`          | ``str(u)``                             |
    +-----------------------------+----------------------------------------+
    | :class:`pathlib.Path`       | ``str(p)``                             |
    +-----------------------------+----------------------------------------+
    | :class:`datetime.datetime`  | result of calling                      |
    |                             | :meth:`~datetime.datetime.isoformat`   |
    +-----------------------------+----------------------------------------+
    | :class:`pydantic.BaseModel` | encoded after calling ``model_dump()`` |
    |                             | in "python" mode                       |
    +-----------------------------+----------------------------------------+

    https://url.spec.whatwg.org/#application/x-www-form-urlencoded

    .. warning::

       Types that are not explicitly mentioned above will result in
       :meth:`to_bytes` simply calling ``str(value)`` and encoding
       the result.  This causes nested sequences to be encoded as
       their ``repr``.  For example, encoding ``{'a': [1, 2]}`` will
       result in ``a=%5B1%2C%202%5D``.  This matches what
       :func:`urllib.parse.urlencode` does by default.

       Better support for sequence values can be enabled by setting
       the :attr:`~FormUrlEncodingOptions.encode_sequences` attribute
       of :attr:`.options`.  This mimics the ``doseq`` parameter of
       :func:`urllib,parse.urlencode`.

    .. attribute:: options
       :type: FormUrlEncodingOptions

       Controls the behavior of the transcoder

    """

    content_type = 'application/x-www-formurlencoded'

    def __init__(self, **encoding_options: typing.Any) -> None:  # noqa: ANN401
        self.options = FormUrlEncodingOptions(**encoding_options)

    def to_bytes(
        self,
        inst_data: type_info.Serializable,
        encoding: typing.Optional[str] = None,
    ) -> typing.Tuple[str, bytes]:
        """Serialize `inst_data` into a byte stream and content type spec.

        :param inst_data: the data to serialize
        :param encoding: optional encoding override

        Serialization is implemented as described in the W3C
        `urlencoded serialization`_ algorithm.  The :attr:`.options`
        attribute controls the configurable details of the encoding
        process.

        The character encoding can be further overridden by specifying the
        `encoding` parameter.

        :returns: tuple of the content type and the resulting bytes
        :raises: :exc:`TypeError` if a supplied value cannot be serialized

        .. _urlencoded serialization: https://url.spec.whatwg.org/
           #urlencoded-serializing

        """
        # Select the appropriate encoding table and use the default
        # character encoding if necessary.  Binding these to local
        # names removes branches from the inner loop.
        chr_map: typing.Mapping[int, str]
        chr_map = (
            _FORM_URLENCODING_PLUS
            if self.options.space_as_plus
            else _FORM_URLENCODING
        )
        if encoding is None:
            encoding = self.options.encoding

        # Generate a sequence of name+value tuples to encode or
        # directly encode primitives
        try:
            tuples = self._convert_to_tuple_sequence(inst_data)
        except TypeError:
            # hopefully this is a primitive ... if not then the
            # call to _encode will fail below
            tuples = [(inst_data, None)]

        prefix = ''  # another micro-optimization
        buf = []
        for name, value in tuples:
            buf.append(prefix)
            buf.extend(self._encode(name, chr_map, encoding))
            if value is not None:
                buf.append('=')
                buf.extend(self._encode(value, chr_map, encoding))
            prefix = '&'
        encoded = ''.join(buf)

        return self.content_type, encoded.encode('ascii')

    def from_bytes(
        self, data_bytes: bytes, encoding: typing.Optional[str] = None
    ) -> type_info.Deserialized:
        """Deserialize `bytes` into a Python object instance.

        :param data_bytes: byte string to deserialize
        :param encoding: optional encoding override

        Deserialization is implemented according to the W3C
        `urlencoded deserialization`_ algorithm.  The :attr:`.options`
        attribute controls the configurable details of the encoding
        process.

        :returns: the decoded Python object

        .. _urlencoded deserialization: https://url.spec.whatwg.org/
           #urlencoded-parsing

        """
        dequote = (
            urllib.parse.unquote_plus
            if self.options.space_as_plus
            else urllib.parse.unquote
        )
        if encoding is None:
            encoding = self.options.encoding

        output = []
        for part in data_bytes.decode('ascii').split('&'):
            if not part:
                continue
            name, eq_present, value = part.partition('=')
            name = dequote(name, encoding=encoding)
            if eq_present:
                output.append((name, dequote(value, encoding=encoding)))
            else:
                output.append((name, ''))

        return dict(output)

    def _encode(
        self,
        datum: typing.Union[
            bool, None, float, int, str, type_info.DefinesIsoFormat
        ],
        char_map: typing.Mapping[int, str],
        encoding: str,
    ) -> str:
        if isinstance(datum, str):
            pass  # optimization: skip additional checks for strings
        elif isinstance(
            datum, (float, int, str, uuid.UUID)
        ) and not isinstance(datum, bool):
            datum = str(datum)
        elif (
            isinstance(datum, collections.abc.Hashable)
            and datum in self.options.literal_mapping
        ):
            # the isinstance Hashable check confuses mypy
            datum = self.options.literal_mapping[datum]  # type: ignore
        elif isinstance(datum, (bytearray, bytes, memoryview)):
            return ''.join(char_map[c] for c in datum)
        elif isinstance(datum, type_info.DefinesIsoFormat):
            datum = datum.isoformat()
        else:
            datum = str(datum)

        return ''.join(char_map[c] for c in datum.encode(encoding))

    def _convert_to_tuple_sequence(
        self, value: type_info.Serializable
    ) -> typing.Iterable[typing.Tuple[typing.Any, typing.Any]]:
        tuples: typing.Iterable[typing.Tuple[typing.Any, typing.Any]]
        if pydantic is not None and isinstance(value, pydantic.BaseModel):
            value = value.model_dump(mode='python')
        if dataclasses.is_dataclass(value):
            value = dataclasses.asdict(value)
        if isinstance(value, collections.abc.Mapping):
            tuples = value.items()
        else:
            try:
                tuples = [(a, b) for a, b in value]  # type: ignore
            except (TypeError, ValueError) as e:
                raise TypeError(
                    'Cannot convert value to sequence of tuples'
                ) from e

        if self.options.encode_sequences:
            out_tuples: list[typing.Tuple[typing.Any, typing.Any]] = []
            for a, b in tuples:
                if not isinstance(
                    b, (bytes, bytearray, memoryview, str)
                ) and isinstance(b, collections.abc.Iterable):
                    out_tuples.extend((a, elm) for elm in b)
                else:
                    out_tuples.append((a, b))
            tuples = out_tuples

        return tuples
