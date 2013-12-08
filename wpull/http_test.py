import io
import tornado.testing
import unittest

from wpull.http import (Request, decode_chunked_transfer, Connection,
    NetworkError, ProtocolError, Client, ConnectionPool)
from wpull.testing.badapp import BadAppTestCase


class TestConnection(BadAppTestCase):
    @tornado.testing.gen_test
    def test_no_such_host(self):
        connection = Connection('wpull-no-exist.invalid', 80)
        try:
            yield connection.fetch(
                Request.new('http://wpull-no-exist.invalid'))
        except NetworkError:
            pass
        else:
            self.assertTrue(False)

    @tornado.testing.gen_test
    def test_connection_refused(self):
        connection = Connection('localhost', 1)
        try:
            yield connection.fetch(
                Request.new('http://localhost:1/'))
        except NetworkError:
            pass
        else:
            self.assertTrue(False)

    @tornado.testing.gen_test
    def test_connection_reuse(self):
        connection = Connection('localhost', self._port)
        request = Request.new(self.get_url('/'))
        request.version = 'HTTP/1.0'
        response = yield connection.fetch(request)
        self.assertEqual(200, response.status_code)
        response = yield connection.fetch(request)
        self.assertEqual(200, response.status_code)

    @tornado.testing.gen_test
    def test_basic(self):
        response = yield self.fetch('/')
        self.assertEqual(200, response.status_code)
        self.assertEqual(b'hello world!', response.body.content)

    @tornado.testing.gen_test
    def test_basic_content_length(self):
        response = yield self.fetch('/content_length')
        self.assertEqual(200, response.status_code)
        self.assertEqual('100', response.fields['Content-Length'])
        self.assertEqual(b'a' * 100, response.body.content)

    @tornado.testing.gen_test
    def test_basic_chunked(self):
        response = yield self.fetch('/chunked')
        self.assertEqual(200, response.status_code)
        self.assertEqual('chunked', response.fields['Transfer-Encoding'])
        self.assertEqual(b'hello world!', response.body.content)

    @tornado.testing.gen_test
    def test_basic_chunked_trailer(self):
        response = yield self.fetch('/chunked_trailer')
        self.assertEqual(200, response.status_code)
        self.assertEqual('chunked', response.fields['Transfer-Encoding'])
        self.assertEqual('dolphin', response.fields['Animal'])
        self.assertEqual(b'hello world!', response.body.content)

    @unittest.skip('TODO: need better way of checking malformed')
    @tornado.testing.gen_test
    def test_malformed_chunked(self):
        try:
            yield self.fetch('/malformed_chunked')
        except ProtocolError:
            pass
        else:
            self.assertTrue(False)

    @tornado.testing.gen_test
    def test_buffer_overflow(self):
        try:
            yield self.fetch('/buffer_overflow')
        except ProtocolError:
            pass
        else:
            self.assertTrue(False)

    @tornado.testing.gen_test
    def test_content_length_and_chunked(self):
        response = yield self.fetch('/content_length_and_chunked')
        self.assertEqual(200, response.status_code)
        self.assertEqual('chunked', response.fields['Transfer-Encoding'])
        self.assertEqual(b'hello world!', response.body.content)

    @tornado.testing.gen_test
    def test_bad_header_delminators(self):
        response = yield self.fetch('/bad_header_deliminators')
        self.assertEqual(200, response.status_code)
        self.assertEqual(b'hi\n', response.body.content)

    @tornado.testing.gen_test
    def test_utf8_header(self):
        response = yield self.fetch('/utf8_header')
        self.assertEqual(200, response.status_code)
        self.assertEqual('🐱', response.fields['whoa'])


class TestClient(BadAppTestCase):
    @tornado.testing.gen_test
    def test_connection_pool_min(self):
        connection_pool = ConnectionPool()
        client = Client(connection_pool)

        for dummy in range(2):
            response = yield client.fetch(
                Request.new(self.get_url('/sleep_short')))
            self.assertEqual(200, response.status_code)

        self.assertEqual(1, len(connection_pool))
        connection_pool_entry = list(connection_pool.values())[0]
        self.assertIsInstance(connection_pool_entry, ConnectionPool.Entry)
        self.assertEqual(1, len(connection_pool_entry.pool))

    @tornado.testing.gen_test
    def test_connection_pool_max(self):
        connection_pool = ConnectionPool()
        client = Client(connection_pool)
        requests = [client.fetch(
            Request.new(self.get_url('/sleep_short'))) for dummy in range(6)]
        responses = yield requests

        for response in responses:
            self.assertEqual(200, response.status_code)

        self.assertEqual(1, len(connection_pool))
        connection_pool_entry = list(connection_pool.values())[0]
        self.assertIsInstance(connection_pool_entry, ConnectionPool.Entry)
        self.assertEqual(6, len(connection_pool_entry.pool))

    @tornado.testing.gen_test
    def test_connection_pool_over_max(self):
        connection_pool = ConnectionPool()
        client = Client(connection_pool)
        requests = [client.fetch(
            Request.new(self.get_url('/sleep_short'))) for dummy in range(12)]
        responses = yield requests

        for response in responses:
            self.assertEqual(200, response.status_code)

        self.assertEqual(1, len(connection_pool))
        connection_pool_entry = list(connection_pool.values())[0]
        self.assertIsInstance(connection_pool_entry, ConnectionPool.Entry)
        self.assertEqual(6, len(connection_pool_entry.pool))

    @tornado.testing.gen_test
    def test_client_exception_throw(self):
        client = Client()

        try:
            yield client.fetch(Request.new('http://wpull-no-exist.invalid'))
        except NetworkError:
            pass
        else:
            self.assertTrue(False)


class TestHTTP(unittest.TestCase):
    def test_request(self):
        request = Request.new('http://example.com/robots.txt')
        self.assertEqual(
            (b'GET /robots.txt HTTP/1.1\r\n'
            b'Host: example.com\r\n'
            b'\r\n'),
            bytes(request)
        )

    def test_decode_chunked_transfer(self):
        input_file = io.BytesIO(b'4\r\n'
            b'Wiki\r\n'
            b'5\r\n'
            b'pedia\r\n'
            b'e\r\n'
            b' in\r\n\r\nchunks.\r\n'
            b'0\r\n'
            b'\r\n')
        decoded = b'Wikipedia in\r\n\r\nchunks.'
        self.assertEqual(decoded, decode_chunked_transfer(input_file).read())