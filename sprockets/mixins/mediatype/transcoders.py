"""
Bundled media type transcoders.

- :class:`.JSONTranscoder` implements JSON encoding/decoding
- :class:`.MsgPackTranscoder` implements msgpack encoding/decoding

"""
import base64
import json
import uuid

import collections

try:
    import umsgpack
except ImportError:
    umsgpack = None

from sprockets.mixins.mediatype import handlers


class JSONTranscoder(handlers.TextContentHandler):
    """
    JSON transcoder instance.

    :param str content_type: the content type that this encoder instance
        implements. If omitted, ``application/json`` is used. This is
        passed directly to the ``TextContentHandler`` initializer.
    :param str default_encoding: the encoding to use if none is specified.
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
    def __init__(self,
                 content_type='application/json',
                 default_encoding='utf-8'):
        super().__init__(content_type, self.dumps, self.loads,
                         default_encoding)
        self.dump_options = {
            'default': self.dump_object,
            'separators': (',', ':'),
        }
        self.load_options = {}

    def dumps(self, obj):
        """
        Dump a :class:`object` instance into a JSON :class:`str`

        :param object obj: the object to dump
        :return: the JSON representation of :class:`object`

        """
        return json.dumps(obj, **self.dump_options)

    def loads(self, str_repr):
        """
        Transform :class:`str` into an :class:`object` instance.

        :param str str_repr: the UNICODE representation of an object
        :return: the decoded :class:`object` representation

        """
        return json.loads(str_repr, **self.load_options)

    def dump_object(self, obj):
        """
        Called to encode unrecognized object.

        :param object obj: the object to encode
        :return: the encoded object
        :raises TypeError: when `obj` cannot be encoded

        This method is passed as the ``default`` keyword parameter
        to :func:`json.dumps`.  It provides default representations for
        a number of Python language/standard library types.

        +----------------------------+---------------------------------------+
        | Python Type                | String Format                         |
        +----------------------------+---------------------------------------+
        | :class:`bytes`,            | Base64 encoded string.                |
        | :class:`bytearray`,        |                                       |
        | :class:`memoryview`        |                                       |
        +----------------------------+---------------------------------------+
        | :class:`datetime.datetime` | ISO8601 formatted timestamp in the    |
        |                            | extended format including separators, |
        |                            | milliseconds, and the timezone        |
        |                            | designator.                           |
        +----------------------------+---------------------------------------+
        | :class:`uuid.UUID`         | Same as ``str(value)``                |
        +----------------------------+---------------------------------------+

        """
        if isinstance(obj, uuid.UUID):
            return str(obj)
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        if isinstance(obj, (bytes, bytearray, memoryview)):
            return base64.b64encode(obj).decode('ASCII')
        raise TypeError('{!r} is not JSON serializable'.format(obj))


class MsgPackTranscoder(handlers.BinaryContentHandler):
    """
    Msgpack Transcoder instance.

    :param str content_type: the content type that this encoder instance
        implements. If omitted, ``application/msgpack`` is used. This
        is passed directly to the ``BinaryContentHandler`` initializer.

    This transcoder uses the `umsgpack`_ library to encode and decode
    objects according to the `msgpack format`_.

    .. _umsgpack: https://github.com/vsergeev/u-msgpack-python
    .. _msgpack format: http://msgpack.org/index.html

    """
    PACKABLE_TYPES = (bool, int, float)

    def __init__(self, content_type='application/msgpack'):
        if umsgpack is None:
            raise RuntimeError('Cannot import MsgPackTranscoder, '
                               'umsgpack is not available')

        super().__init__(content_type, self.packb, self.unpackb)

    def packb(self, data):
        """Pack `data` into a :class:`bytes` instance."""
        return umsgpack.packb(self.normalize_datum(data))

    def unpackb(self, data):
        """Unpack a :class:`object` from a :class:`bytes` instance."""
        return umsgpack.unpackb(data)

    def normalize_datum(self, datum):
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
        if datum is None:
            return datum

        if isinstance(datum, self.PACKABLE_TYPES):
            return datum

        if isinstance(datum, uuid.UUID):
            datum = str(datum)

        if isinstance(datum, bytearray):
            datum = bytes(datum)

        if isinstance(datum, memoryview):
            datum = datum.tobytes()

        if hasattr(datum, 'isoformat'):
            datum = datum.isoformat()

        if isinstance(datum, (bytes, str)):
            return datum

        if isinstance(datum, (collections.abc.Sequence, collections.abc.Set)):
            return [self.normalize_datum(item) for item in datum]

        if isinstance(datum, collections.abc.Mapping):
            out = {}
            for k, v in datum.items():
                out[k] = self.normalize_datum(v)
            return out

        raise TypeError('{} is not msgpackable'.format(
            datum.__class__.__name__))
