Version History
===============

:compare:`Next <3.0.4...master>`
--------------------------------
- **Bump minimum Python version to 3.9**
- Add a transcoder for `application/x-www-formurlencoded`_
- Add support for encoding more types: :class:`decimal.Decimal`, `pydantic.BaseModel`,
  :class:`dataclasses.dataclass`, :class:`array.array`, :class:`enum.Enum`, and
  :class:`datetime.timedelta` annotated types
- Add type annotations (see :ref:`type-info`)
- Return a "406 Not Acceptable" if the :http:header:`Accept` header values cannot be matched
  and there is no default content type configured
- Deprecate not having a default content type configured
- Fail gracefully when a transcoder does not exist for the default content type
- Fail gracefully when a transcoder raises a :exc:`TypeError` or :exc:`ValueError` when encoding
  the response
- Remove setuptools, replace with :pep:`517` and hatch_
- Replace flake8 with ruff
- Replace yapf with ruff

.. _application/x-www-formurlencoded: https://url.spec.whatwg.org/#application/x-www-form-urlencoded
.. _hatch: https://hatch.pypa.io/latest/

:compare:`3.0.4 <3.0.3...3.0.4>` (2 Nov 2020)
---------------------------------------------
- Return a "400 Bad Request" when an invalid Content-Type header is received
  instead of failing with an internal server error

:compare:`3.0.3 <3.0.2...3.0.3>` (14 Sep 2020)
----------------------------------------------
- Import from collections.abc instead of collections (thanks @nullsvm)

:compare:`3.0.2 <3.0.1...3.0.2>` (4 May 2020)
---------------------------------------------
- Do not log tracebacks when decoding the request body fails

:compare:`3.0.1 <3.0.0...3.0.1>` (5 Mar 2019)
---------------------------------------------
- Set Tornado PIN to >=5, <7
- Remove setuptools_scm

:compare:`3.0.0 <2.2.2...3.0.0>` (4 Dec 2018)
---------------------------------------------
- Add MessagePack dependencies to package extras (eg. `pip install sprockets.mixins.mediatype[msgpack]`)
- Update to minimum of ietfparse 1.5.1
- Drop support for Python < 3.7
- Drop support for Tornado < 5
- Remove deprecated :meth:`sprockets.mixins.mediatype.content.ContentSettings.from_application`.

:compare:`2.2.2 <2.2.1...2.2.2>` (7 Apr 2018)
---------------------------------------------
- Add support for Python 3.5 through 3.7
- Add support for Tornado < 6

:compare:`2.2.1 <2.2.0...2.2.1>` (12 Apr 2018)
----------------------------------------------
- Pin :mod:`ietfparse` to avoid breakages introduced in 1.5.0.

:compare:`2.2.0 <2.1.0...2.2.0>` (7 Jun 2017)
---------------------------------------------
- Add :func:`sprockets.mixins.mediatype.content.install`.
- Add :func:`sprockets.mixins.mediatype.content.get_settings`.
- Deprecate :meth:`sprockets.mixins.mediatype.content.ContentSettings.from_application`.
- Update to ietfparse 1.4.

:compare:`2.1.0 <2.0.1...2.1.0>` (16 Mar 2016)
----------------------------------------------
- Set the :http:header:`Vary` header if we are setting the content type.

:compare:`2.0.1 <2.0.0...2.0.1>` (29 Feb 2016)
----------------------------------------------
- Removed deprecation wrapper since it seems to cause really interesting
  problems including the much feared meta-class error.

:compare:`2.0.0 <1.0.4...2.0.0>` (24 Feb 2016)
----------------------------------------------
- Repackage from a module into a package.  Distributing raw modules inside
  of a namespace package is unreliable and questionably correct.
- Add :func:`sprockets.mixins.mediatype.content.add_transcoder`.
- Add :class:`sprockets.mixins.mediatype.transcoders.JSONTranscoder`.
- Add :class:`sprockets.mixins.mediatype.transcoders.MsgPackTranscoder`.
- Add :class:`sprockets.mixins.mediatype.transcoders.BinaryWrapper`.
- Normalize registered MIME types.
- Raise a 400 status when content body decoding fails.

:compare:`1.0.4 <1.0.3...1.0.4>` (14 Sep 2015)
----------------------------------------------
- Support using the default_content_type in the settings if request does not
  contain the Accept header

:compare:`1.0.3 <1.0.2...1.0.3>` (10 Sep 2015)
----------------------------------------------
- Update installation files

:compare:`1.0.2 <1.0.1...1.0.2>` (9 Sep 2015)
---------------------------------------------
- Rename package to mediatype

:compare:`1.0.1 <1.0.0...1.0.1>` (9 Sep 2015)
---------------------------------------------
- Repackaged for Travis-CI configuration.

:compare:`1.0.0 <0.0.0...1.0.0>` (9 Sep 2015)
---------------------------------------------
- Initial Release
