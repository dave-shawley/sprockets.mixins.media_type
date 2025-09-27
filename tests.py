from __future__ import annotations

import array
import base64
import collections
import dataclasses
import datetime
import decimal
import enum
import http
import ipaddress
import json
import os
import pathlib
import pickle
import struct
import sys
import typing
import unittest.mock
import urllib.parse
import uuid

import pydantic
import umsgpack
from ietfparse import algorithms
from tornado import httputil, testing, web

import examples
from sprockets.mixins.mediatype import (
    content,
    handlers,
    transcoders,
    type_info,
)


class Context:
    """Super simple class to call setattr on"""

    def __init__(self) -> None:
        self.settings: dict[str, object] = {}


@dataclasses.dataclass
class Event:
    """Simple dataclass for testing serialization"""

    event: str
    when: datetime.datetime


Point = collections.namedtuple('Point', ['x', 'y'])


class PointClass(typing.NamedTuple):
    x: float
    y: float


if sys.version_info >= (3, 11):  # pragma: no cover

    class Color(enum.StrEnum):
        RED = 'red'
        GREEN = 'green'
        BLUE = 'blue'
else:  # pragma: no cover

    class Color(enum.Enum):
        RED = 'red'
        GREEN = 'green'
        BLUE = 'blue'


def pack_string(obj: object) -> bytes:
    """Optimally pack a string according to msgpack format"""
    payload = str(obj).encode('ASCII')
    pl = len(payload)
    if pl < (2**5):
        prefix = struct.pack('B', 0b10100000 | pl)
    elif pl < (2**8):
        prefix = struct.pack('BB', 0xD9, pl)
    elif pl < (2**16):
        prefix = struct.pack('>BH', 0xDA, pl)
    else:
        prefix = struct.pack('>BI', 0xDB, pl)
    return prefix + payload


def pack_bytes(payload: bytes | bytearray) -> bytes:
    """Optimally pack a byte string according to msgpack format"""
    pl = len(payload)
    if pl < (2**8):
        prefix = struct.pack('BB', 0xC4, pl)
    elif pl < (2**16):
        prefix = struct.pack('>BH', 0xC5, pl)
    else:
        prefix = struct.pack('>BI', 0xC6, pl)
    return prefix + payload


T = typing.TypeVar('T')


def unwrap_as(cls: type[T], obj: object) -> T:
    """Unwrap an object as an instance of the given class

    Use this instead of self.assertIsInstance() and mypy will know that
    the object is of the expected type and not None.

    """
    if not isinstance(obj, cls):
        raise AssertionError(  # noqa: TRY004
            f'expected {cls.__name__}, got {type(obj).__name__}'
        )
    return obj


class TestCase(testing.AsyncHTTPTestCase):
    application: web.Application

    def setUp(self) -> None:
        self.application = None  # type:ignore[assignment]
        super().setUp()

    def get_app(self) -> web.Application:
        self.application = examples.make_application()
        return self.application


class SendResponseTests(TestCase):
    def test_that_content_type_default_works(self) -> None:
        response = self.fetch(
            '/',
            method='POST',
            body='{}',
            headers={'Content-Type': 'application/json'},
        )
        self.assertEqual(response.code, 200)
        self.assertEqual(
            response.headers['Content-Type'],
            'application/json; charset="utf-8"',
        )

    def test_that_missing_content_type_uses_default(self) -> None:
        response = self.fetch(
            '/',
            method='POST',
            body='{}',
            headers={
                'Accept': 'application/xml',
                'Content-Type': 'application/json',
            },
        )
        self.assertEqual(response.code, 200)
        self.assertEqual(
            response.headers['Content-Type'],
            'application/json; charset="utf-8"',
        )

    def test_that_accept_header_is_obeyed(self) -> None:
        response = self.fetch(
            '/',
            method='POST',
            body='{}',
            headers={
                'Accept': 'application/msgpack',
                'Content-Type': 'application/json',
            },
        )
        self.assertEqual(response.code, 200)
        self.assertEqual(
            response.headers['Content-Type'], 'application/msgpack'
        )

    def test_that_default_content_type_is_set_on_response(self) -> None:
        response = self.fetch(
            '/',
            method='POST',
            body=umsgpack.packb({}),
            headers={'Content-Type': 'application/msgpack'},
        )
        self.assertEqual(response.code, 200)
        self.assertEqual(
            response.headers['Content-Type'],
            'application/json; charset="utf-8"',
        )

    def test_that_vary_header_is_set(self) -> None:
        response = self.fetch(
            '/',
            method='POST',
            body=umsgpack.packb({}),
            headers={'Content-Type': 'application/msgpack'},
        )
        self.assertEqual(response.code, 200)
        self.assertEqual(response.headers['Vary'], 'Accept')

    def test_that_accept_header_with_suffix_is_obeyed(self) -> None:
        content.add_transcoder(
            self._app,
            transcoders.MsgPackTranscoder(content_type='expected/content'),
            'application/vendor+msgpack',
        )
        response = self.fetch(
            '/',
            method='POST',
            body='{}',
            headers={
                'Accept': 'application/vendor+msgpack',
                'Content-Type': 'application/json',
            },
        )
        self.assertEqual(response.code, 200)
        self.assertEqual(response.headers['Content-Type'], 'expected/content')

    def test_that_no_default_content_type_will_406(self) -> None:
        # NB if the Accept header is omitted, then a default of `*/*` will
        # be used which results in a match against any registered handler.
        # Using an accept header forces the "no match" case.
        settings = content.get_settings(self.application, force_instance=True)
        settings.default_content_type = None
        settings.default_encoding = None
        response = self.fetch(
            '/',
            method='POST',
            body='{}',
            headers={
                'Accept': 'application/xml',
                'Content-Type': 'application/json',
            },
        )
        self.assertEqual(response.code, 406)

    def test_misconfigured_default_content_type(self) -> None:
        settings = content.get_settings(self.application, force_instance=True)
        settings.default_content_type = 'application/xml'
        response = self.fetch(
            '/',
            method='POST',
            body='{}',
            headers={'Content-Type': 'application/json'},
        )
        self.assertEqual(response.code, 500)

    def test_that_response_content_type_can_be_set(self) -> None:
        class FooGenerator(content.ContentMixin, web.RequestHandler):
            def get(self) -> None:
                self.set_header('Content-Type', 'application/foo+json')
                self.send_response({'foo': 'bar'}, set_content_type=False)

        self.application.add_handlers(r'.*', [web.url(r'/foo', FooGenerator)])
        response = self.fetch('/foo')
        self.assertEqual(200, response.code)
        self.assertEqual(
            'application/foo+json', response.headers.get('Content-Type')
        )

    def test_that_transcoder_failures_result_in_500(self) -> None:
        class FailingTranscoder:
            content_type = 'application/vnd.com.example.bad'

            def __init__(self) -> None:
                self.exc_class: type[Exception] = TypeError

            def to_bytes(
                self, inst_data: object, encoding: object = None
            ) -> typing.NoReturn:
                raise self.exc_class('I always fail at this')

            def from_bytes(
                self, data_bytes: bytes, encoding: object = None
            ) -> dict[str, object]:
                return {}

        transcoder = FailingTranscoder()
        content.add_transcoder(self.application, transcoder)
        for _ in range(2):
            response = self.fetch(
                '/',
                method='POST',
                body=b'{}',
                headers={
                    'Accept': 'application/vnd.com.example.bad',
                    'Content-Type': 'application/json',
                },
            )
            self.assertEqual(500, response.code)
            self.assertEqual('Response Encoding Failure', response.reason)
            transcoder.exc_class = ValueError


class GetRequestBodyTests(TestCase):
    def test_that_request_with_unhandled_type_results_in_415(self) -> None:
        response = self.fetch(
            '/',
            method='POST',
            headers={'Content-Type': 'application/xml'},
            body=(
                '<request><name>value</name>'
                '<embedded><utf8>\u2731</utf8></embedded>'
                '</request>'
            ).encode('utf-8'),
        )
        self.assertEqual(response.code, 415)

    def test_that_msgpack_request_returns_default_type(self) -> None:
        body = {'name': 'value', 'embedded': {'utf8': '\u2731'}}
        response = self.fetch(
            '/',
            method='POST',
            body=umsgpack.packb(body),
            headers={'Content-Type': 'application/msgpack'},
        )
        self.assertEqual(response.code, 200)
        self.assertEqual(json.loads(response.body.decode('utf-8')), body)

    def test_that_invalid_data_returns_400(self) -> None:
        response = self.fetch(
            '/',
            method='POST',
            headers={'Content-Type': 'application/json'},
            body=(
                '<?xml version="1.0"?><methodCall><methodName>echo'
                '</methodName><params><param><value><str>Hi</str></value>'
                '</param></params></methodCall>'
            ).encode('utf-8'),
        )
        self.assertEqual(response.code, 400)

    def test_that_content_type_suffix_is_handled(self) -> None:
        content.add_transcoder(
            self._app, transcoders.JSONTranscoder(), 'application/vendor+json'
        )
        body = {'hello': 'world'}
        response = self.fetch(
            '/',
            method='POST',
            body=json.dumps(body),
            headers={'Content-Type': 'application/vendor+json'},
        )
        self.assertEqual(response.code, 200)
        self.assertEqual(json.loads(response.body.decode()), body)

    def test_that_invalid_content_types_result_in_bad_request(self) -> None:
        content.set_default_content_type(self.application, None, None)  # type: ignore[arg-type]
        response = self.fetch(
            '/',
            method='POST',
            body='{"hi":"there"}',
            headers={'Content-Type': 'application-json'},
        )
        self.assertEqual(response.code, 400)


class MixinCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()

        self.transcoder = transcoders.JSONTranscoder()

        application = unittest.mock.Mock()
        application.settings = {}
        application.ui_methods = {}
        content.install(application, 'application/json', 'utf-8')
        content.add_transcoder(application, self.transcoder)

        request = httputil.HTTPServerRequest(
            'POST',
            '/',
            body=b'{}',
            connection=unittest.mock.Mock(),
            headers=httputil.HTTPHeaders({'Content-Type': 'application/json'}),
        )

        self.handler = content.ContentMixin(application, request)

    def test_that_best_response_type_is_cached(self) -> None:
        with unittest.mock.patch(
            'sprockets.mixins.mediatype.content.algorithms.'
            'select_content_type',
            side_effect=algorithms.select_content_type,
        ) as select_content_type:
            first = self.handler.get_response_content_type()
            second = self.handler.get_response_content_type()

            self.assertIs(first, second)
            self.assertEqual(1, select_content_type.call_count)

    def test_that_request_body_is_cached(self) -> None:
        self.transcoder.from_bytes = unittest.mock.Mock(  # type: ignore[method-assign]
            wraps=self.transcoder.from_bytes
        )
        first = self.handler.get_request_body()
        second = self.handler.get_request_body()
        self.assertIs(first, second)
        self.assertEqual(1, self.transcoder.from_bytes.call_count)


class TypeCoverageTestCase(unittest.TestCase):
    test_cases: list[
        tuple[
            type_info.Serializable,
            bytes | str | int | float | bool | None | list[object],
        ]
    ]
    transcoder: type_info.Transcoder

    def setUp(self) -> None:
        super().setUp()
        now = datetime.datetime.now(datetime.timezone.utc)
        some_id = uuid.uuid4()
        self.test_cases = [
            (12, 12),
            (12.3, 12.3),
            (' string with spaces ', ' string with spaces '),
            (now, now.isoformat()),
            (now.date(), now.date().isoformat()),
            (now.time(), now.time().isoformat()),
            (some_id, str(some_id)),
            (True, True),
            (False, False),
            (None, None),
            (pathlib.Path('/home/user/file.txt'), '/home/user/file.txt'),
            (ipaddress.IPv4Address('192.168.1.1'), '192.168.1.1'),
            (ipaddress.IPv6Address('2001:db8::1'), '2001:db8::1'),
        ]

    def format_value(self, value: object) -> object:
        return value

    def test_serializable_types(self) -> None:
        if not hasattr(self, 'transcoder'):
            self.skipTest('Transcoder not available')
        for serializable, value in self.test_cases:
            expected = self.format_value(value)
            dict_value = {'value': serializable}
            _, encoded = self.transcoder.to_bytes(dict_value)
            decoded = unwrap_as(dict, self.transcoder.from_bytes(encoded))
            actual = decoded['value']
            self.assertEqual(
                expected,
                actual,
                msg=f'Failed for {type(serializable).__name__}',
            )
            self.assertIsInstance(
                actual,
                type(expected),
                msg=f'Wrong type generated for {type(serializable).__name__}',
            )


class JSONTranscoderTests(TypeCoverageTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.transcoder = transcoders.JSONTranscoder()
        ba = bytearray(os.urandom(127))
        mv = memoryview(os.urandom(324))
        pi = decimal.Decimal('3.142857142857142857142857143')
        point = Point(3, 4)
        typed_point = PointClass(3, 4)
        self.test_cases.extend(
            [
                (ba, base64.b64encode(ba).decode('ASCII')),
                (mv, base64.b64encode(mv).decode('ASCII')),
                (pi, float(pi)),
                (array.array('i', [1, 2, 3, 4, 5]), [1, 2, 3, 4, 5]),
                (point, [3, 4]),
                (typed_point, [3, 4]),
                ({1, 2, 3, 4, 5}, [1, 2, 3, 4, 5]),
            ]
        )

    def test_that_unhandled_objects_raise_type_error(self) -> None:
        with self.assertRaises(TypeError):
            self.transcoder.to_bytes(object())  # type: ignore[arg-type]

    def test_that_dataclasses_are_recursively_converted_to_dicts(self) -> None:
        expected = Event(
            'Something Happened', datetime.datetime.now(datetime.timezone.utc)
        )
        _, dumped = self.transcoder.to_bytes(expected)
        loaded = json.loads(dumped)
        self.assertEqual(expected.event, loaded['event'])
        self.assertEqual(expected.when.isoformat(), loaded['when'])

    def test_enum_support(self) -> None:
        status = http.HTTPStatus.OK
        _, dumped = self.transcoder.to_bytes(status)
        int_value = unwrap_as(int, json.loads(dumped))
        self.assertEqual(status.value, int_value)
        self.assertEqual(status, http.HTTPStatus(int_value))

        colors = (Color.RED, Color.GREEN)
        _, dumped = self.transcoder.to_bytes(colors)
        list_value = unwrap_as(list, json.loads(dumped))
        self.assertEqual([c.value for c in colors], list_value)
        self.assertEqual(list(colors), [Color(c) for c in list_value])


class ContentSettingsTests(unittest.TestCase):
    def test_that_handler_listed_in_available_content_types(self) -> None:
        settings = content.ContentSettings()
        settings['application/json'] = unittest.mock.Mock()
        self.assertEqual(len(settings.available_content_types), 1)
        self.assertEqual(
            settings.available_content_types[0].content_type, 'application'
        )
        self.assertEqual(
            settings.available_content_types[0].content_subtype, 'json'
        )

    def test_that_handler_is_not_overwritten(self) -> None:
        settings = content.ContentSettings()
        handler = unittest.mock.Mock()
        settings['application/json'] = handler
        settings['application/json'] = unittest.mock.Mock()
        self.assertIs(settings.get('application/json'), handler)

    def test_that_registered_content_types_are_normalized(self) -> None:
        settings = content.ContentSettings()
        handler = unittest.mock.Mock()
        settings['application/json; VerSion=foo; type=WhatEver'] = handler
        self.assertIs(
            settings['application/json; type=whatever; version=foo'], handler
        )
        self.assertIn(
            'application/json; type=whatever; version=foo',
            (str(c) for c in settings.available_content_types),
        )

    def test_that_normalized_content_types_do_not_overwrite(self) -> None:
        settings = content.ContentSettings()
        handler = unittest.mock.Mock()
        settings['application/json; charset=UTF-8'] = handler
        settings['application/json; charset=utf-8'] = unittest.mock.Mock()
        self.assertEqual(len(settings.available_content_types), 1)
        self.assertEqual(
            settings.available_content_types[0].content_type, 'application'
        )
        self.assertEqual(
            settings.available_content_types[0].content_subtype, 'json'
        )
        self.assertEqual(settings['application/json; charset=utf-8'], handler)

    def test_that_setting_no_default_content_type_warns(self) -> None:
        settings = content.ContentSettings()
        with self.assertWarns(DeprecationWarning):
            settings.default_content_type = None


class ContentFunctionTests(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.context = Context()

    def test_that_add_binary_content_type_creates_binary_handler(self) -> None:
        settings = content.install(self.context, 'application/octet-stream')
        content.add_binary_content_type(
            self.context,
            'application/vnd.python.pickle',
            pickle.dumps,
            pickle.loads,
        )
        transcoder = unwrap_as(
            handlers.BinaryContentHandler,
            settings['application/vnd.python.pickle'],
        )
        self.assertIs(transcoder._pack, pickle.dumps)
        self.assertIs(transcoder._unpack, pickle.loads)

    def test_that_add_text_content_type_creates_text_handler(self) -> None:
        settings = content.install(self.context, 'application/json')
        content.add_text_content_type(
            self.context, 'application/json', 'utf8', json.dumps, json.loads
        )
        transcoder = unwrap_as(
            handlers.TextContentHandler, settings['application/json']
        )
        self.assertIs(transcoder._dumps, json.dumps)
        self.assertIs(transcoder._loads, json.loads)

    def test_that_add_text_content_type_discards_charset_parameter(
        self,
    ) -> None:
        settings = content.install(self.context, 'application/json', 'utf-8')
        content.add_text_content_type(
            self.context,
            'application/json;charset=UTF-8',
            'utf8',
            json.dumps,
            json.loads,
        )
        transcoder = settings['application/json']
        self.assertIsInstance(transcoder, handlers.TextContentHandler)

    def test_that_install_creates_settings(self) -> None:
        settings = content.install(self.context, 'application/json', 'utf8')
        self.assertIsNotNone(settings)
        self.assertEqual(settings.default_content_type, 'application/json')
        self.assertEqual(settings.default_encoding, 'utf8')

    def test_that_get_settings_returns_none_when_no_settings(self) -> None:
        settings = content.get_settings(self.context)
        self.assertIsNone(settings)

    def test_that_get_settings_returns_installed_settings(self) -> None:
        settings = content.install(self.context, 'application/xml', 'utf8')
        other_settings = content.get_settings(self.context)
        self.assertIs(settings, other_settings)

    def test_that_get_settings_will_create_instance_if_requested(self) -> None:
        settings = content.get_settings(self.context, force_instance=True)
        self.assertIsNotNone(settings)
        self.assertIs(content.get_settings(self.context), settings)


class MsgPackTranscoderTests(TypeCoverageTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.transcoder = transcoders.MsgPackTranscoder()
        random_bytes = os.urandom(127)
        pi = decimal.Decimal('3.142857142857142857142857143')
        self.test_cases.extend(
            [
                (array.array('i', [1, 2, 3, 4, 5]), [1, 2, 3, 4, 5]),
                (Point(1, 2), [1, 2]),
                (PointClass(3, 4), [3, 4]),
                (http.HTTPStatus.OK, 200),
                (
                    [Color.RED, Color.GREEN],
                    [Color.RED.value, Color.GREEN.value],
                ),
                (random_bytes, random_bytes),
                (bytearray(random_bytes), random_bytes),
                (memoryview(random_bytes), random_bytes),
                (pi, float(pi)),
            ]
        )

    def assert_packed_value_equals(
        self, value: type_info.Serializable, expected: bytes
    ) -> None:
        _, actual = self.transcoder.to_bytes(value)
        self.assertEqual(expected, actual)

    def test_that_strings_are_dumped_as_strings(self) -> None:
        self.assert_packed_value_equals('foo', pack_string('foo'))

    def test_that_none_is_packed_as_nil_byte(self) -> None:
        self.assert_packed_value_equals(None, b'\xc0')

    def test_that_bools_are_dumped_appropriately(self) -> None:
        self.assert_packed_value_equals(False, b'\xc2')
        self.assert_packed_value_equals(True, b'\xc3')

    def test_that_ints_are_packed_appropriately(self) -> None:
        self.assert_packed_value_equals(2**7 - 1, b'\x7f')
        self.assert_packed_value_equals(2**7, b'\xcc\x80')
        self.assert_packed_value_equals(2**8, b'\xcd\x01\x00')
        self.assert_packed_value_equals(2**16, b'\xce\x00\x01\x00\x00')
        self.assert_packed_value_equals(
            2**32, b'\xcf\x00\x00\x00\x01\x00\x00\x00\x00'
        )

    def test_that_negative_ints_are_packed_accordingly(self) -> None:
        self.assert_packed_value_equals(-(2**0), b'\xff')
        self.assert_packed_value_equals(-(2**5), b'\xe0')
        self.assert_packed_value_equals(-(2**7), b'\xd0\x80')
        self.assert_packed_value_equals(-(2**15), b'\xd1\x80\x00')
        self.assert_packed_value_equals(-(2**31), b'\xd2\x80\x00\x00\x00')
        self.assert_packed_value_equals(
            -(2**63), b'\xd3\x80\x00\x00\x00\x00\x00\x00\x00'
        )

    def test_that_lists_are_treated_as_arrays(self) -> None:
        self.assert_packed_value_equals([], b'\x90')

    def test_that_tuples_are_treated_as_arrays(self) -> None:
        self.assert_packed_value_equals((), b'\x90')

    def test_that_sets_are_treated_as_arrays(self) -> None:
        self.assert_packed_value_equals(set(), b'\x90')

    def test_that_unhandled_objects_raise_type_error(self) -> None:
        with self.assertRaises(TypeError):
            self.transcoder.to_bytes(object())  # type: ignore[arg-type]

    def test_that_utf8_values_can_be_forced_to_bytes(self) -> None:
        data = b'a ascii value'
        self.assert_packed_value_equals(data, pack_bytes(data))

    def test_that_dicts_are_sent_as_maps(self) -> None:
        data = {'compact': True, 'schema': 0}
        self.assert_packed_value_equals(
            data, b'\x82\xa7compact\xc3\xa6schema\x00'
        )

    def test_that_transcoder_creation_fails_if_umsgpack_is_missing(
        self,
    ) -> None:
        with (
            unittest.mock.patch(
                'sprockets.mixins.mediatype.transcoders.umsgpack',
                new_callable=lambda: None,
            ),
            self.assertRaises(RuntimeError),
        ):
            transcoders.MsgPackTranscoder()

    def test_that_decimals_are_converted_to_floats(self) -> None:
        pi = decimal.Decimal('3.142857142857142857142857143')
        # 0xCB -> 8 byte IEEE float in big endian order
        self.assert_packed_value_equals(
            pi, b'\xcb' + struct.pack('>d', float(pi))
        )

    def test_that_dataclasses_are_dumped_as_mappings(self) -> None:
        when = datetime.datetime.now(datetime.timezone.utc)
        event = Event('Something Happened', when)
        self.assert_packed_value_equals(
            event,
            b'\x82\xa5event\xb2Something Happened\xa4when'
            + pack_string(when.isoformat()),
        )


class FormUrlEncodingTranscoderTests(TypeCoverageTestCase):
    transcoder: type_info.Transcoder

    def setUp(self) -> None:
        super().setUp()
        self.transcoder = transcoders.FormUrlEncodedTranscoder()
        pi = decimal.Decimal('3.142857142857142857142857143')
        self.test_cases.extend([(pi, str(pi))])

    def format_value(self, value: object) -> object:
        if isinstance(value, bool):
            return str(value).lower()
        if value is None:
            return ''
        return str(value)

    def test_simple_deserialization(self) -> None:
        body = typing.cast(
            'dict[str, object]',
            self.transcoder.from_bytes(
                b'number=12&boolean=true&null=null&string=any%20thing&empty='
            ),
        )
        self.assertEqual(body['number'], '12')
        self.assertEqual(body['boolean'], 'true')
        self.assertEqual(body['empty'], '')
        self.assertEqual(body['null'], 'null')
        self.assertEqual(body['string'], 'any thing')

    def test_deserialization_edge_cases(self) -> None:
        body = self.transcoder.from_bytes(b'')
        self.assertEqual({}, body)

        body = self.transcoder.from_bytes(b'&')
        self.assertEqual({}, body)

        body = self.transcoder.from_bytes(b'empty&&=no-name&no-value=')
        self.assertEqual({'empty': '', '': 'no-name', 'no-value': ''}, body)

        body = self.transcoder.from_bytes(b'repeated=1&repeated=2')
        self.assertEqual({'repeated': '2'}, body)

    def test_that_deserialization_encoding_can_be_overridden(self) -> None:
        body = self.transcoder.from_bytes(
            b'kolor=%bf%F3%b3ty', encoding='iso-8859-2'
        )
        self.assertEqual({'kolor': 'żółty'}, body)

    def test_that_serialization_encoding_can_be_overridden(self) -> None:
        _, result = self.transcoder.to_bytes(
            [('kolor', 'żółty')], encoding='iso-8859-2'
        )
        self.assertEqual(b'kolor=%bf%f3%b3ty', result.lower())

    def test_serialization_edge_cases(self) -> None:
        _, result = self.transcoder.to_bytes(
            [
                ('', ''),
                ('', True),
                ('', False),
                ('', None),
                ('name', None),
            ]
        )
        self.assertEqual(b'=&=true&=false&&name', result)

    def test_serialization_using_plusses(self) -> None:
        transcoder = unwrap_as(
            transcoders.FormUrlEncodedTranscoder, self.transcoder
        )

        transcoder.options.space_as_plus = True
        _, result = transcoder.to_bytes({'value': 'with space'})
        self.assertEqual(b'value=with+space', result)

        transcoder.options.space_as_plus = False
        _, result = transcoder.to_bytes({'value': 'with space'})
        self.assertEqual(b'value=with%20space', result)

    def test_that_serializing_unsupported_types_stringifies(self) -> None:
        obj = object()
        # quick & dirty URL encoding
        expected = str(obj).translate({0x20: '%20', 0x3C: '%3C', 0x3E: '%3E'})

        _, result = self.transcoder.to_bytes({'unsupported': obj})
        self.assertEqual(f'unsupported={expected}'.encode(), result)

    def test_that_required_octets_are_encoded(self) -> None:
        # build the set of all characters required to be encoded by
        # https://url.spec.whatwg.org/#percent-encoded-bytes
        pct_chrs = typing.cast('typing.Set[str]', set())
        pct_chrs.update(set(' "#<>'))  # query set
        pct_chrs.update(set('?`{}'))  # path set
        pct_chrs.update(set('/:;=@[^|'))  # userinfo set
        pct_chrs.update(set('$%&+,'))  # component set
        pct_chrs.update(set("!'()~"))  # formurlencoding set

        test_string = ''.join(pct_chrs)
        expected = ''.join('%{:02X}'.format(ord(c)) for c in test_string)
        expected = f'test_string={expected}'
        _, result = self.transcoder.to_bytes({'test_string': test_string})
        self.assertEqual(expected.encode(), result)

    def test_serialization_of_primitives(self) -> None:
        expectations = {
            None: b'',
            'a string': b'a%20string',
            True: b'true',
            False: b'false',
            b'\xfe\xed\xfa\xce': b'%FE%ED%FA%CE',
            memoryview(b'\xfe\xed\xfa\xce'): b'%FE%ED%FA%CE',
        }
        for value, expected in expectations.items():
            _, result = self.transcoder.to_bytes(value)
            self.assertEqual(expected, result)

    def test_serialization_with_empty_literal_map(self) -> None:
        transcoder = unwrap_as(
            transcoders.FormUrlEncodedTranscoder, self.transcoder
        )
        transcoder.options.literal_mapping.clear()
        for value in (None, True, False):
            _, result = self.transcoder.to_bytes(value)
            self.assertEqual(str(value).encode(), result)

    def test_serialization_of_sequences(self) -> None:
        value = {'list': [1, 2], 'tuple': (1, 2), 'set': {1, 2}, 'str': 'val'}

        transcoder = unwrap_as(
            transcoders.FormUrlEncodedTranscoder, self.transcoder
        )
        transcoder.options.encode_sequences = False
        _, result = transcoder.to_bytes(value)
        self.assertEqual(
            (
                b'list=%5B1%2C%202%5D&tuple=%281%2C%202%29'
                b'&set=%7B1%2C%202%7D&str=val'
            ),
            result,
        )

        transcoder.options.encode_sequences = True
        _, result = transcoder.to_bytes(value)
        self.assertEqual(
            b'list=1&list=2&tuple=1&tuple=2&set=1&set=2&str=val', result
        )

    def test_that_arrays_are_serialized_as_sequences(self) -> None:
        transcoder = transcoders.FormUrlEncodedTranscoder()
        transcoder.options.encode_sequences = True
        arr = array.array('i', [1, 2, 3])
        _, result = transcoder.to_bytes({'arr': arr})
        self.assertEqual(b'arr=1&arr=2&arr=3', result)

    def test_that_named_tuples_are_treated_as_sequences(self) -> None:
        transcoder = transcoders.FormUrlEncodedTranscoder()
        transcoder.options.encode_sequences = True
        point = Point(3, 4)
        _, result = transcoder.to_bytes({'point': point})
        self.assertEqual(b'point=3&point=4', result)

        typed_point = PointClass(3, 4)
        _, result = transcoder.to_bytes({'point': typed_point})
        self.assertEqual(b'point=3&point=4', result)

    def test_that_dataclasses_are_serialized(self) -> None:
        when = datetime.datetime.now(datetime.timezone.utc)
        event = Event('Something Happened', when)
        _, result = self.transcoder.to_bytes(event)
        self.assertEqual(
            b'event=Something%20Happened&when='
            + urllib.parse.quote(when.isoformat()).encode(),
            result,
        )


class Item(pydantic.BaseModel):
    name: str
    price: float


class WarehouseBin(pydantic.BaseModel):
    location: str
    last_verified: datetime.datetime
    items: list[Item] = pydantic.Field(default_factory=list)


class PydanticSupportTests(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        now = datetime.datetime.now(datetime.timezone.utc)
        self.payload = WarehouseBin.model_validate(
            {
                'location': 'A1',
                'last_verified': now,
                'items': [
                    {'name': 'Widget', 'price': 10.0},
                    {'name': 'Gadget', 'price': 20.0},
                ],
            }
        )
        self.normalized = self.payload.model_dump(mode='python')
        self.normalized['last_verified'] = now.isoformat()

    def test_json_dumping(self) -> None:
        transcoder = transcoders.JSONTranscoder()
        _, result = transcoder.to_bytes(self.payload)
        self.assertEqual(self.normalized, json.loads(result.decode()))
        self.assertEqual(
            self.payload,
            WarehouseBin.model_validate(json.loads(result.decode())),
        )

    def test_msgpack_dumping(self) -> None:
        transcoder = transcoders.MsgPackTranscoder()
        _, result = transcoder.to_bytes(self.payload)
        self.assertEqual(self.normalized, umsgpack.unpackb(result))
        self.assertEqual(
            self.payload,
            WarehouseBin.model_validate(umsgpack.unpackb(result)),
        )

    def test_form_url_encoded_dumping(self) -> None:
        transcoder = transcoders.FormUrlEncodedTranscoder(
            encode_sequences=True
        )
        _, result = transcoder.to_bytes(self.payload)

        expected = urllib.parse.urlencode(
            self.normalized, doseq=True, quote_via=urllib.parse.quote
        )
        self.assertEqual(expected.encode(), result)
