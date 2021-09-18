import base64
import datetime
import json
import os
import pickle
import struct
import unittest
import uuid

from tornado import testing
import umsgpack

from sprockets.mixins.mediatype import content, handlers, transcoders
import examples


class UTC(datetime.tzinfo):
    ZERO = datetime.timedelta(0)

    def utcoffset(self, dt):
        return self.ZERO

    def dst(self, dt):
        return self.ZERO

    def tzname(self, dt):
        return 'UTC'


class Context:
    """Super simple class to call setattr on"""
    def __init__(self):
        self.settings = {}


def pack_string(obj):
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


def pack_bytes(payload):
    """Optimally pack a byte string according to msgpack format"""
    pl = len(payload)
    if pl < (2**8):
        prefix = struct.pack('BB', 0xC4, pl)
    elif pl < (2**16):
        prefix = struct.pack('>BH', 0xC5, pl)
    else:
        prefix = struct.pack('>BI', 0xC6, pl)
    return prefix + payload


class SendResponseTests(testing.AsyncHTTPTestCase):
    def get_app(self):
        return examples.make_application()

    def test_that_content_type_default_works(self):
        response = self.fetch('/',
                              method='POST',
                              body='{}',
                              headers={'Content-Type': 'application/json'})
        self.assertEqual(response.code, 200)
        self.assertEqual(response.headers['Content-Type'],
                         'application/json; charset="utf-8"')

    def test_that_missing_content_type_uses_default(self):
        response = self.fetch('/',
                              method='POST',
                              body='{}',
                              headers={
                                  'Accept': 'application/xml',
                                  'Content-Type': 'application/json'
                              })
        self.assertEqual(response.code, 200)
        self.assertEqual(response.headers['Content-Type'],
                         'application/json; charset="utf-8"')

    def test_that_accept_header_is_obeyed(self):
        response = self.fetch('/',
                              method='POST',
                              body='{}',
                              headers={
                                  'Accept': 'application/msgpack',
                                  'Content-Type': 'application/json'
                              })
        self.assertEqual(response.code, 200)
        self.assertEqual(response.headers['Content-Type'],
                         'application/msgpack')

    def test_that_default_content_type_is_set_on_response(self):
        response = self.fetch('/',
                              method='POST',
                              body=umsgpack.packb({}),
                              headers={'Content-Type': 'application/msgpack'})
        self.assertEqual(response.code, 200)
        self.assertEqual(response.headers['Content-Type'],
                         'application/json; charset="utf-8"')

    def test_that_vary_header_is_set(self):
        response = self.fetch('/',
                              method='POST',
                              body=umsgpack.packb({}),
                              headers={'Content-Type': 'application/msgpack'})
        self.assertEqual(response.code, 200)
        self.assertEqual(response.headers['Vary'], 'Accept')

    def test_that_accept_header_with_suffix_is_obeyed(self):
        content.add_transcoder(
            self._app,
            transcoders.MsgPackTranscoder(content_type='expected/content'),
            'application/vendor+msgpack')
        response = self.fetch('/',
                              method='POST',
                              body='{}',
                              headers={
                                  'Accept': 'application/vendor+msgpack',
                                  'Content-Type': 'application/json'
                              })
        self.assertEqual(response.code, 200)
        self.assertEqual(response.headers['Content-Type'], 'expected/content')


class GetRequestBodyTests(testing.AsyncHTTPTestCase):
    def setUp(self):
        self.app = None
        super().setUp()

    def get_app(self):
        self.app = examples.make_application()
        return self.app

    def test_that_request_with_unhandled_type_results_in_415(self):
        response = self.fetch('/',
                              method='POST',
                              headers={'Content-Type': 'application/xml'},
                              body=('<request><name>value</name>'
                                    '<embedded><utf8>\u2731</utf8></embedded>'
                                    '</request>').encode('utf-8'))
        self.assertEqual(response.code, 415)

    def test_that_msgpack_request_returns_default_type(self):
        body = {'name': 'value', 'embedded': {'utf8': '\u2731'}}
        response = self.fetch('/',
                              method='POST',
                              body=umsgpack.packb(body),
                              headers={'Content-Type': 'application/msgpack'})
        self.assertEqual(response.code, 200)
        self.assertEqual(json.loads(response.body.decode('utf-8')), body)

    def test_that_invalid_data_returns_400(self):
        response = self.fetch(
            '/',
            method='POST',
            headers={'Content-Type': 'application/json'},
            body=('<?xml version="1.0"?><methodCall><methodName>echo'
                  '</methodName><params><param><value><str>Hi</str></value>'
                  '</param></params></methodCall>').encode('utf-8'))
        self.assertEqual(response.code, 400)

    def test_that_content_type_suffix_is_handled(self):
        content.add_transcoder(self._app, transcoders.JSONTranscoder(),
                               'application/vendor+json')
        body = {'hello': 'world'}
        response = self.fetch(
            '/',
            method='POST',
            body=json.dumps(body),
            headers={'Content-Type': 'application/vendor+json'})
        self.assertEqual(response.code, 200)
        self.assertEqual(json.loads(response.body.decode()), body)

    def test_that_invalid_content_types_result_in_bad_request(self):
        content.set_default_content_type(self.app, None, None)
        response = self.fetch('/',
                              method='POST',
                              body='{"hi":"there"}',
                              headers={'Content-Type': 'application-json'})
        self.assertEqual(response.code, 400)


class JSONTranscoderTests(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.transcoder = transcoders.JSONTranscoder()

    def test_that_uuids_are_dumped_as_strings(self):
        obj = {'id': uuid.uuid4()}
        dumped = self.transcoder.dumps(obj)
        self.assertEqual(dumped.replace(' ', ''), '{"id":"%s"}' % obj['id'])

    def test_that_datetimes_are_dumped_in_isoformat(self):
        obj = {'now': datetime.datetime.now()}
        dumped = self.transcoder.dumps(obj)
        self.assertEqual(dumped.replace(' ', ''),
                         '{"now":"%s"}' % obj['now'].isoformat())

    def test_that_tzaware_datetimes_include_tzoffset(self):
        obj = {'now': datetime.datetime.now().replace(tzinfo=UTC())}
        self.assertTrue(obj['now'].isoformat().endswith('+00:00'))
        dumped = self.transcoder.dumps(obj)
        self.assertEqual(dumped.replace(' ', ''),
                         '{"now":"%s"}' % obj['now'].isoformat())

    def test_that_bytearrays_are_base64_encoded(self):
        bin = bytearray(os.urandom(127))
        dumped = self.transcoder.dumps({'bin': bin})
        self.assertEqual(
            dumped, '{"bin":"%s"}' % base64.b64encode(bin).decode('ASCII'))

    def test_that_memoryviews_are_base64_encoded(self):
        bin = memoryview(os.urandom(127))
        dumped = self.transcoder.dumps({'bin': bin})
        self.assertEqual(
            dumped, '{"bin":"%s"}' % base64.b64encode(bin).decode('ASCII'))

    def test_that_unhandled_objects_raise_type_error(self):
        with self.assertRaises(TypeError):
            self.transcoder.dumps(object())


class ContentSettingsTests(unittest.TestCase):
    def test_that_handler_listed_in_available_content_types(self):
        settings = content.ContentSettings()
        settings['application/json'] = object()
        self.assertEqual(len(settings.available_content_types), 1)
        self.assertEqual(settings.available_content_types[0].content_type,
                         'application')
        self.assertEqual(settings.available_content_types[0].content_subtype,
                         'json')

    def test_that_handler_is_not_overwritten(self):
        settings = content.ContentSettings()
        settings['application/json'] = handler = object()
        settings['application/json'] = object()
        self.assertIs(settings.get('application/json'), handler)

    def test_that_registered_content_types_are_normalized(self):
        settings = content.ContentSettings()
        handler = object()
        settings['application/json; VerSion=foo; type=WhatEver'] = handler
        self.assertIs(settings['application/json; type=whatever; version=foo'],
                      handler)
        self.assertIn('application/json; type=whatever; version=foo',
                      (str(c) for c in settings.available_content_types))

    def test_that_normalized_content_types_do_not_overwrite(self):
        settings = content.ContentSettings()
        settings['application/json; charset=UTF-8'] = handler = object()
        settings['application/json; charset=utf-8'] = object()
        self.assertEqual(len(settings.available_content_types), 1)
        self.assertEqual(settings.available_content_types[0].content_type,
                         'application')
        self.assertEqual(settings.available_content_types[0].content_subtype,
                         'json')
        self.assertEqual(settings['application/json; charset=utf-8'], handler)


class ContentFunctionTests(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.context = Context()

    def test_that_add_binary_content_type_creates_binary_handler(self):
        settings = content.install(self.context, 'application/octet-stream')
        content.add_binary_content_type(self.context,
                                        'application/vnd.python.pickle',
                                        pickle.dumps, pickle.loads)
        transcoder = settings['application/vnd.python.pickle']
        self.assertIsInstance(transcoder, handlers.BinaryContentHandler)
        self.assertIs(transcoder._pack, pickle.dumps)
        self.assertIs(transcoder._unpack, pickle.loads)

    def test_that_add_text_content_type_creates_text_handler(self):
        settings = content.install(self.context, 'application/json')
        content.add_text_content_type(self.context, 'application/json', 'utf8',
                                      json.dumps, json.loads)
        transcoder = settings['application/json']
        self.assertIsInstance(transcoder, handlers.TextContentHandler)
        self.assertIs(transcoder._dumps, json.dumps)
        self.assertIs(transcoder._loads, json.loads)

    def test_that_add_text_content_type_discards_charset_parameter(self):
        settings = content.install(self.context, 'application/json', 'utf-8')
        content.add_text_content_type(self.context,
                                      'application/json;charset=UTF-8', 'utf8',
                                      json.dumps, json.loads)
        transcoder = settings['application/json']
        self.assertIsInstance(transcoder, handlers.TextContentHandler)

    def test_that_install_creates_settings(self):
        settings = content.install(self.context, 'application/json', 'utf8')
        self.assertIsNotNone(settings)
        self.assertEqual(settings.default_content_type, 'application/json')
        self.assertEqual(settings.default_encoding, 'utf8')

    def test_that_get_settings_returns_none_when_no_settings(self):
        settings = content.get_settings(self.context)
        self.assertIsNone(settings)

    def test_that_get_settings_returns_installed_settings(self):
        settings = content.install(self.context, 'application/xml', 'utf8')
        other_settings = content.get_settings(self.context)
        self.assertIs(settings, other_settings)

    def test_that_get_settings_will_create_instance_if_requested(self):
        settings = content.get_settings(self.context, force_instance=True)
        self.assertIsNotNone(settings)
        self.assertIs(content.get_settings(self.context), settings)


class MsgPackTranscoderTests(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.transcoder = transcoders.MsgPackTranscoder()

    def test_that_strings_are_dumped_as_strings(self):
        dumped = self.transcoder.packb('foo')
        self.assertEqual(self.transcoder.unpackb(dumped), 'foo')
        self.assertEqual(dumped, pack_string('foo'))

    def test_that_none_is_packed_as_nil_byte(self):
        self.assertEqual(self.transcoder.packb(None), b'\xC0')

    def test_that_bools_are_dumped_appropriately(self):
        self.assertEqual(self.transcoder.packb(False), b'\xC2')
        self.assertEqual(self.transcoder.packb(True), b'\xC3')

    def test_that_ints_are_packed_appropriately(self):
        self.assertEqual(self.transcoder.packb((2**7) - 1), b'\x7F')
        self.assertEqual(self.transcoder.packb(2**7), b'\xCC\x80')
        self.assertEqual(self.transcoder.packb(2**8), b'\xCD\x01\x00')
        self.assertEqual(self.transcoder.packb(2**16), b'\xCE\x00\x01\x00\x00')
        self.assertEqual(self.transcoder.packb(2**32),
                         b'\xCF\x00\x00\x00\x01\x00\x00\x00\x00')

    def test_that_negative_ints_are_packed_accordingly(self):
        self.assertEqual(self.transcoder.packb(-(2**0)), b'\xFF')
        self.assertEqual(self.transcoder.packb(-(2**5)), b'\xE0')
        self.assertEqual(self.transcoder.packb(-(2**7)), b'\xD0\x80')
        self.assertEqual(self.transcoder.packb(-(2**15)), b'\xD1\x80\x00')
        self.assertEqual(self.transcoder.packb(-(2**31)),
                         b'\xD2\x80\x00\x00\x00')
        self.assertEqual(self.transcoder.packb(-(2**63)),
                         b'\xD3\x80\x00\x00\x00\x00\x00\x00\x00')

    def test_that_lists_are_treated_as_arrays(self):
        dumped = self.transcoder.packb(list())
        self.assertEqual(self.transcoder.unpackb(dumped), [])
        self.assertEqual(dumped, b'\x90')

    def test_that_tuples_are_treated_as_arrays(self):
        dumped = self.transcoder.packb(tuple())
        self.assertEqual(self.transcoder.unpackb(dumped), [])
        self.assertEqual(dumped, b'\x90')

    def test_that_sets_are_treated_as_arrays(self):
        dumped = self.transcoder.packb(set())
        self.assertEqual(self.transcoder.unpackb(dumped), [])
        self.assertEqual(dumped, b'\x90')

    def test_that_unhandled_objects_raise_type_error(self):
        with self.assertRaises(TypeError):
            self.transcoder.packb(object())

    def test_that_uuids_are_dumped_as_strings(self):
        uid = uuid.uuid4()
        dumped = self.transcoder.packb(uid)
        self.assertEqual(self.transcoder.unpackb(dumped), str(uid))
        self.assertEqual(dumped, pack_string(uid))

    def test_that_datetimes_are_dumped_in_isoformat(self):
        now = datetime.datetime.now()
        dumped = self.transcoder.packb(now)
        self.assertEqual(self.transcoder.unpackb(dumped), now.isoformat())
        self.assertEqual(dumped, pack_string(now.isoformat()))

    def test_that_tzaware_datetimes_include_tzoffset(self):
        now = datetime.datetime.now().replace(tzinfo=UTC())
        self.assertTrue(now.isoformat().endswith('+00:00'))
        dumped = self.transcoder.packb(now)
        self.assertEqual(self.transcoder.unpackb(dumped), now.isoformat())
        self.assertEqual(dumped, pack_string(now.isoformat()))

    def test_that_bytes_are_sent_as_bytes(self):
        data = bytes(os.urandom(127))
        dumped = self.transcoder.packb(data)
        self.assertEqual(self.transcoder.unpackb(dumped), data)
        self.assertEqual(dumped, pack_bytes(data))

    def test_that_bytearrays_are_sent_as_bytes(self):
        data = bytearray(os.urandom(127))
        dumped = self.transcoder.packb(data)
        self.assertEqual(self.transcoder.unpackb(dumped), data)
        self.assertEqual(dumped, pack_bytes(data))

    def test_that_memoryviews_are_sent_as_bytes(self):
        data = memoryview(os.urandom(127))
        dumped = self.transcoder.packb(data)
        self.assertEqual(self.transcoder.unpackb(dumped), data)
        self.assertEqual(dumped, pack_bytes(data.tobytes()))

    def test_that_utf8_values_can_be_forced_to_bytes(self):
        data = b'a ascii value'
        dumped = self.transcoder.packb(data)
        self.assertEqual(self.transcoder.unpackb(dumped), data)
        self.assertEqual(dumped, pack_bytes(data))
