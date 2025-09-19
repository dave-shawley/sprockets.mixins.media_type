from __future__ import annotations

import decimal
import typing
import uuid
from collections import abc

try:
    from typing import Protocol, runtime_checkable
except ImportError:
    # "ignore" is required to avoid an incompatible import
    # error due to different bindings of _SpecialForm
    from typing_extensions import Protocol, runtime_checkable


@runtime_checkable
class DefinesIsoFormat(Protocol):
    """An object that has an isoformat method."""

    def isoformat(self) -> str:
        """Return the date/time in ISO-8601 format."""
        ...


@runtime_checkable
class IsDataclass(Protocol):
    """Something that :func:`dataclasses.is_dataclass` recognizes."""

    __dataclass_fields__: typing.ClassVar[dict[str, typing.Any]]


class HasSettings(Protocol):
    """Something that quacks like a tornado.web.Application."""

    settings: typing.Dict[str, typing.Any]
    """Application settings."""


T_Pydantic = typing.TypeVar('T_Pydantic', bound='PydanticModel')


@runtime_checkable
class PydanticModel(Protocol):
    """Class that resembles a pydantic model."""

    @classmethod
    def model_validate(cls: type[T_Pydantic], obj: object) -> T_Pydantic:
        """Validate an object and return a model instance."""
        ...

    def model_dump(self, *, mode: str) -> dict[str, typing.Any]:
        """Serialize the model to a dictionary."""
        ...


SerializablePrimitives = (
    type(None),
    bool,
    bytearray,
    bytes,
    decimal.Decimal,
    float,
    int,
    memoryview,
    str,
    uuid.UUID,
)
"""Use this with isinstance to identify simple values."""

Serializable: typing.TypeAlias = typing.Union[
    DefinesIsoFormat,
    None,
    bool,
    bytearray,
    bytes,
    decimal.Decimal,
    float,
    int,
    memoryview,
    str,
    abc.Mapping[str, object],
    abc.Sequence[object],
    abc.Set[object],
    uuid.UUID,
    IsDataclass,
    PydanticModel,
]
"""Types that can be serialized by this library.

This is the set of types that
:meth:`sprockets.mixins.mediatype.content.ContentMixin.send_response`
is capable for serializing.

"""

Deserialized = typing.Union[
    None, bytes, abc.Mapping[str, object], float, int, list[object], str
]
"""Possible result of deserializing a body.

This is the set of types that
:meth:`sprockets.mixins.mediatype.content.ContentMixin.get_request_body`
might return.

"""

PackBFunction = abc.Callable[[Serializable], bytes]
"""Signature of a binary content handler's serialization hook."""

UnpackBFunction = abc.Callable[[bytes], Deserialized]
"""Signature of a binary content handler's deserialization hook."""

DumpSFunction = abc.Callable[[Serializable], str]
"""Signature of a text content handler's serialization hook."""

LoadSFunction = abc.Callable[[str], Deserialized]
"""Signature of a text content handler's deserialization hook."""

MsgPackable = typing.Union[
    None,
    bool,
    bytes,
    dict[typing.Any, typing.Any],
    float,
    int,
    list[typing.Any],
    str,
]
"""Set of types that the underlying msgpack library can serialize."""


class Transcoder(Protocol):
    """Object that transforms objects to bytes and back again.

    Transcoder instances are identified by their `content_type`
    instance attribute and registered by calling
    :func:`~sprockets.mixins.mediatype.content.add_transcoder`.
    They are used to implement request deserialization
    (:meth:`~sprockets.mixins.mediatype.content.ContentMixin.get_request_body`)
    and response body serialization
    (:meth:`~sprockets.mixins.mediatype.content.ContentMixin.send_response`)

    """

    content_type: str
    """Canonical content type that this transcoder implements."""

    def to_bytes(
        self, inst_data: Serializable, encoding: str | None = None
    ) -> tuple[str, bytes]:
        """Serialize `inst_data` into a byte stream and content type spec.

        :param inst_data: the data to serialize
        :param encoding: optional encoding to use when serializing

        The content type is returned since it may contain the encoding
        or character set as a parameter.  The `encoding` parameter may
        not be used by all transcoders.

        :returns: tuple of the content type and the resulting bytes

        """
        ...

    def from_bytes(
        self, data_bytes: bytes, encoding: str | None = None
    ) -> Deserialized:
        """Deserialize `bytes` into a Python object instance.

        :param data_bytes: byte string to deserialize
        :param encoding: optional encoding to use when deserializing

        The `encoding` parameter may not be used by all transcoders.

        :returns: the decoded Python object

        """
        ...
