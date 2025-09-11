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
from __future__ import annotations

import logging
import typing
import warnings

try:
    from typing import Literal
except ImportError:  # pragma: no cover
    # "ignore" is required to avoid an incompatible import
    # error due to different bindings of _SpecialForm
    from typing_extensions import Literal  # type: ignore

from ietfparse import algorithms, datastructures, errors, headers
from tornado import web

from sprockets.mixins.mediatype import handlers, type_info

logger = logging.getLogger(__name__)
SETTINGS_KEY = 'sprockets.mixins.mediatype.ContentSettings'
"""Key in application.settings to store the ContentSettings instance."""

_warning_issued = False


def _format_content_type(ct: datastructures.ContentType) -> str:
    return (f'{ct.content_type}/{ct.content_subtype}+{ct.content_suffix}' if
            ct.content_suffix else f'{ct.content_type}/{ct.content_subtype}')


class ContentSettings:
    """
    Content selection settings.

    An instance of this class is stashed in ``application.settings``
    under the :data:`.SETTINGS_KEY` key.  Instead of creating an
    instance of this class yourself, use the :func:`.install`
    function to install it into the application.

    The settings instance contains the list of available content
    types and handlers associated with them.  Each handler implements
    the :class:`~sprockets.mixins.mediatype.type_info.Transcoder`
    interface.  Use :func:`add_transcoder` to add support for a
    specific content type to the application.

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
          add_transcoder(app, transcoders.JSONTranscoder())
          add_transcoder(app, transcoders.MsgPackTranscoder())
          return app

    Of course, that is quite tedious, so use the :class:`.ContentMixin`
    instead of using the settings directly.

    """

    default_encoding: typing.Union[str, None]
    _available_types: typing.List[datastructures.ContentType]
    _default_content_type: typing.Union[str, None]
    _handlers: typing.Dict[str, type_info.Transcoder]

    def __init__(self) -> None:
        self._handlers = {}
        self._available_types = []
        self._default_content_type = None
        self.default_encoding = None

    def __getitem__(self, content_type: str) -> type_info.Transcoder:
        parsed = headers.parse_content_type(content_type)
        return self._handlers[str(parsed)]

    def __setitem__(self, content_type: str,
                    handler: type_info.Transcoder) -> None:
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
        default: typing.Union[type_info.Transcoder, None] = None
    ) -> typing.Union[type_info.Transcoder, None]:
        """Retrieve the handler for a specific content type."""
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

    @property
    def default_content_type(self) -> typing.Union[str, None]:
        return self._default_content_type

    @default_content_type.setter
    def default_content_type(self, new_value: typing.Union[str, None]) -> None:
        if new_value is None:
            warnings.warn(DeprecationWarning(
                'Using sprockets.mixins.mediatype without a default'
                ' content type is deprecated and will become an error'
                ' in a future version'),
                          stacklevel=2)
        self._default_content_type = new_value


def install(application: type_info.HasSettings,
            default_content_type: typing.Optional[str],
            encoding: typing.Optional[str] = None) -> ContentSettings:
    """Install the media type management settings and return it"""
    try:
        settings = typing.cast('ContentSettings',
                               application.settings[SETTINGS_KEY])
    except KeyError:
        settings = application.settings[SETTINGS_KEY] = ContentSettings()
        settings.default_content_type = default_content_type
        settings.default_encoding = encoding
    return settings


@typing.overload
def get_settings(
    application: type_info.HasSettings,
    force_instance: Literal[False] = False
) -> typing.Union[ContentSettings, None]:
    ...  # pragma: no cover


@typing.overload
def get_settings(application: type_info.HasSettings,
                 force_instance: Literal[True]) -> ContentSettings:
    ...  # pragma: no cover


def get_settings(
        application: type_info.HasSettings,
        force_instance: bool = False) -> typing.Union[ContentSettings, None]:
    """
    Retrieve the media type settings for a application.

    :param application:
    :param force_instance: if :data:`True` then create the
        instance if it does not exist

    :return: the content settings instance or :data:`None` if
        `force_instance` is not :data:`True` and :func:`.install`
        has not been called

    """
    try:
        return typing.cast('ContentSettings',
                           application.settings[SETTINGS_KEY])
    except KeyError:
        if not force_instance:
            return None
    return install(application, None)


def add_binary_content_type(application: type_info.HasSettings,
                            content_type: str, pack: type_info.PackBFunction,
                            unpack: type_info.UnpackBFunction) -> None:
    """
    Add handler for a binary content type.

    :param application: the application to modify
    :param content_type: the content type to add
    :param pack: function that packs a dictionary to a byte string.
        See :any:`type_info.PackBFunction`
    :param unpack: function that takes a byte string and returns a
        dictionary.  See :any:`type_info.UnpackBFunction`

    """
    add_transcoder(application,
                   handlers.BinaryContentHandler(content_type, pack, unpack))


def add_text_content_type(application: type_info.HasSettings,
                          content_type: str, default_encoding: str,
                          dumps: type_info.DumpSFunction,
                          loads: type_info.LoadSFunction) -> None:
    """
    Add handler for a text content type.

    :param application: the application to modify
    :param content_type: the content type to add
    :param default_encoding: encoding to use when one is unspecified
    :param dumps: function that dumps a dictionary to a string.
        See :any:`type_info.DumpSFunction`
    :param loads: function that loads a dictionary from a string.
        See :any:`type_info.LoadSFunction`

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


def add_transcoder(application: type_info.HasSettings,
                   transcoder: type_info.Transcoder,
                   content_type: typing.Optional[str] = None) -> None:
    """
    Register a transcoder for a specific content type.

    :param application: the application to modify
    :param transcoder: object that translates between :class:`bytes`
        and object instances
    :param content_type: the content type to add.  If this is
        unspecified or :data:`None`, then the transcoder's
        ``content_type`` attribute is used.

    The `transcoder` instance is required to implement the
    :class:`~sprockets.mixins.mediatype.type_info.Transcoder`
    protocol.

    """
    settings = get_settings(application, force_instance=True)
    settings[content_type or transcoder.content_type] = transcoder


def set_default_content_type(application: type_info.HasSettings,
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
    def initialize(self) -> None:
        super().initialize()
        self._request_body: typing.Optional[type_info.Deserialized] = None
        self._best_response_match: typing.Optional[str] = None
        self._logger = getattr(self, 'logger', logger)

    def get_response_content_type(self) -> typing.Union[str, None]:
        """Select the content type will be used in the response.

        This method implements proactive content negotiation as
        described in :rfc:`7231#section-3.4.1` using the
        :http:header:`Accept` request header or the configured
        default content type if the header is not present.  The
        selected response type is cached and returned.  It will
        be used when :meth:`.send_response` is called.

        Note that this method is called by :meth:`.send_response`
        so you will seldom need to call it directly.

        """
        if self._best_response_match is None:
            settings = get_settings(self.application, force_instance=True)
            acceptable = headers.parse_accept(
                self.request.headers.get(
                    'Accept', settings.default_content_type
                    if settings.default_content_type else '*/*'))
            try:
                selected, _ = algorithms.select_content_type(
                    acceptable, settings.available_content_types)
                self._best_response_match = _format_content_type(selected)
            except errors.NoMatch:
                self._best_response_match = settings.default_content_type

        return self._best_response_match

    def get_request_body(self) -> type_info.Deserialized:
        """
        Fetch (and cache) the request body as a dictionary.

        :raise tornado.web.HTTPError:
            - if the content type cannot be matched, then the status code
              is set to 415 Unsupported Media Type.
            - if decoding the content body fails, then the status code is
              set to 400 Bad Syntax.

        """
        if self._request_body is None:
            settings = get_settings(self.application, force_instance=True)
            content_type = self.request.headers.get(
                'Content-Type', settings.default_content_type)

            try:
                content_type_header = headers.parse_content_type(
                    content_type or 'binary/octet-stream')
            except ValueError as e:
                raise web.HTTPError(400, 'failed to parse content type %s',
                                    content_type) from e
            content_type = _format_content_type(content_type_header)
            try:
                handler = settings[content_type]
            except KeyError as e:
                raise web.HTTPError(415, 'cannot decode body of type %s',
                                    content_type) from e

            try:
                self._request_body = handler.from_bytes(self.request.body)
            except Exception as e:
                self._logger.error('failed to decode request body')
                raise web.HTTPError(400, 'failed to decode request') from e

        return self._request_body

    def send_response(self,
                      body: type_info.Serializable,
                      set_content_type: typing.Optional[bool] = True) -> None:
        """
        Serialize and send ``body`` in the response.

        :param body: the body to serialize
        :param set_content_type: should the :http:header:`Content-Type`
            header be set?  Defaults to :data:`True`

        The transcoder for the response is selected by calling
        :meth:`.get_response_content_type` which chooses an
        appropriate transcoder based on the :http:header:`Accept`
        header from the request.

        """
        settings = get_settings(self.application, force_instance=True)
        response_type = self.get_response_content_type()
        if response_type is None:
            self._logger.error('failed to find a suitable response '
                               'content type for request')
            self._logger.error('please set a default content type')
            raise web.HTTPError(406)

        try:
            handler = settings[response_type]
        except KeyError:
            self._logger.error(
                'no transcoder for the selected response content type %s, '
                'is the default content type %r correct?', response_type,
                settings.default_content_type)
            raise web.HTTPError(500) from None
        else:
            try:
                content_type, data_bytes = handler.to_bytes(body)
            except (TypeError, ValueError) as e:
                self._logger.error(
                    'selected transcoder (%s) failed to encode response '
                    'body: %s', handler.__class__.__name__, e)
                raise web.HTTPError(500,
                                    reason='Response Encoding Failure') from e
            else:
                if set_content_type:
                    self.set_header('Content-Type', content_type)
                    self.add_header('Vary', 'Accept')
                self.write(data_bytes)
