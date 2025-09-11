"""
Basic content handlers.

- :class:`BinaryContentHandler` basic transcoder for binary types that
  simply calls functions for encoding and decoding
- :class:`TextContentHandler` transcoder that translates binary bodies
  to text before calling functions that encode & decode text

"""

from __future__ import annotations

import typing

from tornado import escape

if typing.TYPE_CHECKING:
    from sprockets.mixins.mediatype import type_info


class BinaryContentHandler:
    """
    Pack and unpack binary types.

    :param content_type: registered content type
    :param pack: function that transforms an object instance
        into :class:`bytes`
    :param unpack: function that transforms :class:`bytes`
        into an object instance

    This transcoder is a thin veneer around a pair of packing
    and unpacking functions.

    """

    def __init__(
        self,
        content_type: str,
        pack: type_info.PackBFunction,
        unpack: type_info.UnpackBFunction,
    ) -> None:
        self._pack = pack
        self._unpack = unpack
        self.content_type = content_type

    def to_bytes(
        self,
        inst_data: type_info.Serializable,
        encoding: typing.Optional[str] = None,  # noqa: ARG002
    ) -> typing.Tuple[str, bytes]:
        """
        Transform an object into :class:`bytes`.

        :param inst_data: object to encode
        :param encoding: ignored
        :returns: :class:`tuple` of the selected content
            type and the :class:`bytes` representation of
            `inst_data`

        """
        return self.content_type, self._pack(inst_data)

    def from_bytes(
        self,
        data_bytes: bytes,
        encoding: typing.Optional[str] = None,  # noqa: ARG002
    ) -> type_info.Deserialized:
        """
        Get an object from :class:`bytes`

        :param data_bytes: stream of bytes to decode
        :param encoding: ignored
        :returns: decoded :class:`object` instance

        """
        return self._unpack(data_bytes)


class TextContentHandler:
    """
    Transcodes between textual and object representations.

    :param content_type: registered content type
    :param dumps: function that transforms an object instance
        into a :class:`str`
    :param loads: function that transforms a :class:`str`
        into an object instance
    :param default_encoding: encoding to apply when
        transcoding from the underlying body :class:`byte`
        instance

    This transcoder wraps functions that transcode between :class:`str`
    and :class:`object` instances.  In particular, it handles the
    additional step of transcoding into the :class:`byte` instances
    that tornado expects.

    """

    def __init__(
        self,
        content_type: str,
        dumps: type_info.DumpSFunction,
        loads: type_info.LoadSFunction,
        default_encoding: str,
    ) -> None:
        self._dumps = dumps
        self._loads = loads
        self.content_type = content_type
        self.default_encoding = default_encoding

    def to_bytes(
        self,
        inst_data: type_info.Serializable,
        encoding: typing.Optional[str] = None,
    ) -> typing.Tuple[str, bytes]:
        """
        Transform an object into :class:`bytes`.

        :param inst_data: object to encode
        :param encoding: character set used to encode the bytes
            returned from the ``dumps`` function.  This defaults to
            :attr:`default_encoding`
        :returns: :class:`tuple` of the selected content
            type and the :class:`bytes` representation of
            `inst_data`

        """
        selected = encoding or self.default_encoding
        content_type = '{0}; charset="{1}"'.format(self.content_type, selected)
        dumped = self._dumps(escape.recursive_unicode(inst_data))
        return content_type, dumped.encode(selected)

    def from_bytes(
        self, data: bytes, encoding: typing.Optional[str] = None
    ) -> type_info.Deserialized:
        """
        Get an object from :class:`bytes`

        :param data: stream of bytes to decode
        :param encoding: character set used to decode the incoming
            bytes before calling the ``loads`` function.  This defaults
            to :attr:`default_encoding`
        :returns: decoded :class:`object` instance

        """
        return self._loads(data.decode(encoding or self.default_encoding))
