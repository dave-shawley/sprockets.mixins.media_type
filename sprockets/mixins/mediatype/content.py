"""
Content handling for Tornado.

- :func:`.install` creates a settings object and installs it into
  the :class:`tornado.web.Application` instance
- :func:`.get_settings` retrieve a :class:`.ContentSettings` object
  from a :class:`tornado.web.Application` instance
- :func:`.set_default_content_type` sets the content type that is
  used when an ``Accept`` or ``Content-Type`` header is omitted.
- :func:`.add_binary_content_type` register transcoders for a binary
  content type
- :func:`.add_text_content_type` register transcoders for a textual
  content type
- :func:`.add_transcoder` register a custom transcoder instance
  for a content type

- :class:`.ContentSettings` an instance of this is attached to
  :class:`tornado.web.Application` to hold the content mapping
  information for the application
- :class:`.ContentMixin` attaches a :class:`.ContentSettings`
  instance to the application and implements request decoding &
  response encoding methods

This module is the primary interface for this library.  It exposes
functions for registering new content handlers and a mix-in that
adds content handling methods to :class:`~tornado.web.RequestHandler`
instances.

"""
import logging
import typing

from ietfparse import algorithms, datastructures, errors, headers
from tornado import web

from . import handlers, type_info

logger = logging.getLogger(__name__)
SETTINGS_KEY = 'sprockets.mixins.mediatype.ContentSettings'
"""Key in application.settings to store the ContentSettings instance."""

_warning_issued = False


class ContentSettings:
    """
    Content selection settings.

    An instance of this class is stashed in ``application.settings``
    under the :data:`.SETTINGS_KEY` key.  Instead of creating an
    instance of this class yourself, use the :func:`.install`
    function to install it into the application.

    The settings instance contains the list of available content
    types and handlers associated with them.  Each handler implements
    a simple interface:

    - ``to_bytes(dict, encoding:str) -> bytes``
    - ``from_bytes(bytes, encoding:str) -> dict``

    Use the :func:`add_binary_content_type` and :func:`add_text_content_type`
    helper functions to modify the settings for the application.

    This class acts as a mapping from content-type string to the
    appropriate handler instance.  Add new content types and find
    handlers using the common ``dict`` syntax:

    .. code-block:: python

       class SomeHandler(web.RequestHandler):

          def get(self):
             settings = ContentSettings.get_settings(self.application)
             response_body = settings['application/msgpack'].to_bytes(
                response_dict, encoding='utf-8')
             self.write(response_body)

       def make_application():
          app = web.Application([('/', SomeHandler)])
          add_binary_content_type(app, 'application/msgpack',
                                  msgpack.packb, msgpack.unpackb)
          add_text_content_type(app, 'application/json', 'utf-8',
                                json.dumps, json.loads)
          return app

    Of course, that is quite tedious, so use the :class:`.ContentMixin`
    instead.

    """
    default_content_type: typing.Optional[str]
    default_encoding: typing.Optional[str]
    _available_types: typing.List[datastructures.ContentType]
    _handlers: typing.MutableMapping[str, type_info.ContentHandlerProtocol]

    def __init__(self) -> None:
        self._handlers = {}
        self._available_types = []
        self.default_content_type = None
        self.default_encoding = None

    def __getitem__(self,
                    content_type: str) -> type_info.ContentHandlerProtocol:
        parsed = headers.parse_content_type(content_type)
        return self._handlers[str(parsed)]

    def __setitem__(self, content_type: str,
                    handler: type_info.ContentHandlerProtocol) -> None:
        parsed = headers.parse_content_type(content_type)
        content_type = str(parsed)
        if content_type in self._handlers:
            logger.warning('handler for %s already set to %r', content_type,
                           self._handlers[content_type])
            return

        self._available_types.append(parsed)
        self._handlers[content_type] = handler

    def get(
        self,
        content_type: str,
        default: typing.Optional[type_info.ContentHandlerProtocol] = None
    ) -> typing.Union[None, type_info.ContentHandlerProtocol]:
        return self._handlers.get(content_type, default)

    @property
    def available_content_types(
            self) -> typing.Sequence[datastructures.ContentType]:
        """
        List of the content types that are registered.

        This is a sequence of :class:`ietfparse.datastructures.ContentType`
        instances.

        """
        return self._available_types


def install(application: type_info.ApplicationProtocol,
            default_content_type: typing.Optional[str],
            encoding: typing.Optional[str] = None) -> ContentSettings:
    """
    Install the media type management settings.

    :param application: the application to
        install a :class:`.ContentSettings` object into.
    :param default_content_type:
    :param encoding: default encoding

    :returns: the content settings instance

    """
    try:
        settings = typing.cast(ContentSettings,
                               application.settings[SETTINGS_KEY])
    except KeyError:
        settings = application.settings[SETTINGS_KEY] = ContentSettings()
        settings.default_content_type = default_content_type
        settings.default_encoding = encoding
    return settings


@typing.overload
def get_settings(
    application: type_info.ApplicationProtocol,
    force_instance: type_info.Literal[True]
) -> ContentSettings:  # pragma: no cover
    ...


@typing.overload
def get_settings(
    application: type_info.ApplicationProtocol,
    force_instance: type_info.Literal[False]
) -> typing.Optional[ContentSettings]:  # pragma: no cover
    ...


@typing.overload
def get_settings(
    application: type_info.ApplicationProtocol,
    force_instance: bool = False
) -> typing.Optional[ContentSettings]:  # pragma: no cover
    ...


def get_settings(
        application: type_info.ApplicationProtocol,
        force_instance: bool = False) -> typing.Optional[ContentSettings]:
    """
    Retrieve the media type settings for a application.

    :param application: application to fetch the settings for
    :param force_instance: if :data:`True` then create the
        instance if it does not exist

    :return: the content settings instance

    """
    try:
        return typing.cast(ContentSettings, application.settings[SETTINGS_KEY])
    except KeyError:
        if not force_instance:
            return None
    return install(application, None)


def add_binary_content_type(application: type_info.ApplicationProtocol,
                            content_type: str,
                            pack: type_info.PackFunctionType,
                            unpack: type_info.UnpackFunctionType) -> None:
    """
    Add handler for a binary content type.

    :param application: the application to modify
    :param content_type: the content type to add
    :param pack: function that packs a dictionary to a byte string.
        ``pack(dict) -> bytes``
    :param unpack: function that takes a byte string and returns a
        dictionary.  ``unpack(bytes) -> dict``

    """
    add_transcoder(application,
                   handlers.BinaryContentHandler(content_type, pack, unpack))


def add_text_content_type(application: type_info.ApplicationProtocol,
                          content_type: str, default_encoding: str,
                          dumps: type_info.DumpStringFunctionType,
                          loads: type_info.LoadStringFunctionType) -> None:
    """
    Add handler for a text content type.

    :param application: the application to modify
    :param content_type: the content type to add
    :param default_encoding: encoding to use when one is unspecified
    :param dumps: function that dumps a dictionary to a string.
        ``dumps(dict, encoding:str) -> str``
    :param loads: function that loads a dictionary from a string.
        ``loads(str, encoding:str) -> dict``

    Note that the ``charset`` parameter is stripped from `content_type`
    if it is present.

    """
    parsed = headers.parse_content_type(content_type)
    parsed.parameters.pop('charset', None)
    normalized = str(parsed)
    add_transcoder(
        application,
        handlers.TextContentHandler(normalized, dumps, loads,
                                    default_encoding))


def add_transcoder(application: type_info.ApplicationProtocol,
                   transcoder: type_info.ContentHandlerProtocol,
                   content_type: typing.Optional[str] = None) -> None:
    """
    Register a transcoder for a specific content type.

    :param application: the application to modify
    :param transcoder: object that translates between :class:`bytes` and
        :class:`object` instances
    :param content_type: the content type to add.  If this is
        unspecified or :data:`None`, then the transcoder's ``content_type``
        attribute is used.

    The `transcoder` instance is required to implement the following
    simple protocol:

    .. attribute:: transcoder.content_type

       :class:`str` that identifies the MIME type that the transcoder
       implements.

    .. method:: transcoder.to_bytes(inst_data, encoding=None) -> bytes

       :param object inst_data: the object to encode
       :param str encoding: character encoding to apply or :data:`None`
       :returns: the encoded :class:`bytes` instance

    .. method:: transcoder.from_bytes(data_bytes, encoding=None) -> object

       :param bytes data_bytes: the :class:`bytes` instance to decode
       :param str encoding: character encoding to use or :data:`None`
       :returns: the decoded :class:`object` instance

    """
    settings = get_settings(application, force_instance=True)
    settings[content_type or transcoder.content_type] = transcoder


def set_default_content_type(application: type_info.ApplicationProtocol,
                             content_type: str,
                             encoding: typing.Optional[str] = None) -> None:
    """
    Store the default content type for an application.

    :param application: the application to modify
    :param content_type: the content type to default to
    :param encoding: encoding to use when one is unspecified

    """
    settings = get_settings(application, force_instance=True)
    settings.default_content_type = content_type
    settings.default_encoding = encoding


class ContentMixin(web.RequestHandler):
    """
    Mix this in to add some content handling methods.

    .. code-block:: python

       class MyHandler(ContentMixin, web.RequestHandler):
          def post(self):
             body = self.get_request_body()
             # do stuff --> response_dict
             self.send_response(response_dict)

    :meth:`get_request_body` will deserialize the request data into
    a dictionary based on the :http:header:`Content-Type` request
    header.  Similarly, :meth:`send_response` takes a dictionary,
    serializes it based on the :http:header:`Accept` request header
    and the application :class:`ContentSettings`, and writes it out,
    using ``self.write()``.

    """
    _best_response_match: typing.Optional[str]
    _request_body: typing.Optional[type_info.DeserializedType]

    def initialize(self) -> None:
        super().initialize()
        self._request_body = None
        self._best_response_match = None
        self._logger = getattr(self, 'logger', logger)

    def get_response_content_type(self) -> typing.Optional[str]:
        """Figure out what content type will be used in the response."""
        # NB - will return `None` if there is no match AND the default
        # content type for the application is not set
        if self._best_response_match is None:
            settings = get_settings(self.application, force_instance=True)
            acceptable = headers.parse_accept(
                self.request.headers.get(
                    'Accept', settings.default_content_type
                    if settings.default_content_type else '*/*'))
            try:
                selected, _ = algorithms.select_content_type(
                    acceptable, settings.available_content_types)
                self._best_response_match = '/'.join(
                    [selected.content_type, selected.content_subtype])
                if selected.content_suffix is not None:
                    self._best_response_match = '+'.join(
                        [self._best_response_match, selected.content_suffix])
            except errors.NoMatch:
                self._best_response_match = settings.default_content_type

        return self._best_response_match

    def get_request_body(self) -> type_info.DeserializedType:
        """
        Fetch (and cache) the request body.

        :raises: :exc:`tornado.web.HTTPError`

            - if the content type cannot be matched, then the status code
              is set to 415 Unsupported Media Type.
            - if decoding the content body fails, then the status code is
              set to 400 Bad Syntax.

        """
        if self._request_body is None:
            settings = get_settings(self.application, force_instance=True)
            content_type_header = headers.parse_content_type(
                self.request.headers.get('Content-Type',
                                         settings.default_content_type))
            content_type = '/'.join([
                content_type_header.content_type,
                content_type_header.content_subtype
            ])
            if content_type_header.content_suffix is not None:
                content_type = '+'.join(
                    [content_type, content_type_header.content_suffix])
            try:
                handler = settings[content_type]
            except KeyError:
                raise web.HTTPError(415, 'cannot decode body of type %s',
                                    content_type)

            try:
                self._request_body = handler.from_bytes(self.request.body)
            except Exception:
                self._logger.exception('failed to decode request body')
                raise web.HTTPError(400, 'failed to decode request')

        return self._request_body

    def send_response(self,
                      body: type_info.SerializableTypes,
                      set_content_type: bool = True) -> None:
        """
        Serialize and send ``body`` in the response.

        :param body: the body to serialize
        :param set_content_type: should the :http:header:`Content-Type`
            header be set?  Defaults to :data:`True`

        :raises: a :http:statuscode:`415` :exc:`tornado.web.HTTPError`
            if the requested content type cannot be satisfied **AND**
            the default content type is not set

        """
        settings = get_settings(self.application, force_instance=True)
        response_type = self.get_response_content_type()
        if not response_type:
            raise web.HTTPError(415, 'failed to determine content type')

        handler = settings[response_type]
        content_type, data_bytes = handler.to_bytes(body)
        if set_content_type:
            self.set_header('Content-Type', content_type)
            self.add_header('Vary', 'Accept')
        self.write(data_bytes)
