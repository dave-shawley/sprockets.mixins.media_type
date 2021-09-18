"""
Basic content handlers.

- :class:`BinaryContentHandler` basic transcoder for binary types that
  simply calls functions for encoding and decoding
- :class:`TextContentHandler` transcoder that translates binary bodies
  to text before calling functions that encode & decode text

"""
from tornado import escape


class BinaryContentHandler:
    """
    Pack and unpack binary types.

    :param str content_type: registered content type
    :param pack: function that transforms an object instance
        into :class:`bytes`
    :param unpack: function that transforms :class:`bytes`
        into an object instance

    This transcoder is a thin veneer around a pair of packing
    and unpacking functions.

    """
    def __init__(self, content_type, pack, unpack):
        self._pack = pack
        self._unpack = unpack
        self.content_type = content_type

    def to_bytes(self, inst_data, encoding=None):
        """
        Transform an object into :class:`bytes`.

        :param object inst_data: object to encode
        :param str encoding: ignored
        :returns: :class:`tuple` of the selected content
            type and the :class:`bytes` representation of
            `inst_data`

        """
        return self.content_type, self._pack(inst_data)

    def from_bytes(self, data_bytes, encoding=None):
        """
        Get an object from :class:`bytes`

        :param bytes data_bytes: stream of bytes to decode
        :param str encoding: ignored
        :param dict content_parameters: optional :class:`dict` of
            content type parameters from the :mailheader:`Content-Type`
            header
        :returns: decoded :class:`object` instance

        """
        return self._unpack(data_bytes)


class TextContentHandler:
    """
    Transcodes between textual and object representations.

    :param str content_type: registered content type
    :param dumps: function that transforms an object instance
        into a :class:`str`
    :param loads: function that transforms a :class:`str`
        into an object instance
    :param str default_encoding: encoding to apply when
        transcoding from the underlying body :class:`byte`
        instance

    This transcoder wraps functions that transcode between :class:`str`
    and :class:`object` instances.  In particular, it handles the
    additional step of transcoding into the :class:`byte` instances
    that tornado expects.

    """
    def __init__(self, content_type, dumps, loads, default_encoding):
        self._dumps = dumps
        self._loads = loads
        self.content_type = content_type
        self.default_encoding = default_encoding

    def to_bytes(self, inst_data, encoding=None):
        """
        Transform an object into :class:`bytes`.

        :param object inst_data: object to encode
        :param str encoding: character set used to encode the bytes
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

    def from_bytes(self, data, encoding=None):
        """
        Get an object from :class:`bytes`

        :param bytes data: stream of bytes to decode
        :param str encoding: character set used to decode the incoming
            bytes before calling the ``loads`` function.  This defaults
            to :attr:`default_encoding`
        :param dict content_parameters: optional :class:`dict` of
            content type parameters from the :mailheader:`Content-Type`
            header
        :returns: decoded :class:`object` instance

        """
        return self._loads(data.decode(encoding or self.default_encoding))
