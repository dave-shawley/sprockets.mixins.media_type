API Documentation
=================

.. currentmodule:: sprockets.mixins.mediatype.content

The easiest way to use this library is to:

#. call :func:`.install` when you create your application instance and specify a
   default content type
#. call :func:`.add_transcoder` to install transcoders for the content types that
   you support -- use :func:`.add_binary_content_type` and/or
   :func:`.add_text_content_type` if you don't want to define a
   :class:`~sprockets.mixins.mediatype.type_info.Transcoder` class.
#. include :class:`.ContentMixin` in your handler's inheritance chain
#. call :meth:`~.ContentMixin.get_request_body` to retrieve a request body
   sent in any of the supported content types
#. call :meth:`~.ContentMixin.send_response` to send a response in any of the
   supported content types

The :class:`.ContentMixin` will take care of inspecting the :http:header:`Content-Type`
header and deserialize the request as well as implementing the
:rfc:`proactive content negotiation algorithm <7231#section-3.4.1>` described in
:rfc:`7231` to serialize a response object appropriately.

Content Type Handling
---------------------
.. autoclass:: ContentMixin
   :members:

Content Type Registration
-------------------------
.. autofunction:: install

.. autofunction:: add_transcoder

.. autofunction:: set_default_content_type

.. autofunction:: add_binary_content_type

.. autofunction:: add_text_content_type

.. autofunction:: get_settings

.. autoclass:: ContentSettings
   :members:

Bundled Transcoders
-------------------
.. currentmodule:: sprockets.mixins.mediatype.transcoders

.. autoclass:: JSONTranscoder
   :members:

.. autoclass:: MsgPackTranscoder
   :members:

.. autoclass:: FormUrlEncodedTranscoder
   :members:

.. autoclass:: FormUrlEncodingOptions
   :members:

.. _type-info:

Python Type Information
-----------------------
The ``sprockets.mixins.mediatype.type_info`` module contains a number of
convenience type definitions for those you you who take advantage of type
annotations.

.. currentmodule:: sprockets.mixins.mediatype.type_info

Interface Types
~~~~~~~~~~~~~~~

.. autoclass:: Transcoder
   :members:

.. autodata:: Serializable

.. autodata:: Deserialized

Convenience Types
~~~~~~~~~~~~~~~~~

.. autodata:: PackBFunction

.. autodata:: UnpackBFunction

.. autodata:: DumpSFunction

.. autodata:: LoadSFunction

Contract Types
~~~~~~~~~~~~~~

.. autoclass:: HasSettings
   :members:

.. autoclass:: DefinesIsoFormat
   :members:

.. autoclass:: PydanticModel
   :members:
