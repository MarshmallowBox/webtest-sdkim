from http import cookiejar as http_cookiejar
from webob import Request
from webob import Response
from webtest.compat import to_bytes
from collections import OrderedDict
from webtest.debugapp import debug_app
from webtest import http
from tests.compat import unittest
import os
from unittest import mock
import webtest
print('hello')
class TestApp(unittest.TestCase):

    def setUp(self):
        self.app = webtest.TestApp(debug_app)

    def test_pytest_collection_disabled(self):
        self.assertFalse(webtest.TestApp.__test__)

    def test_encode_multipart_relative_to(self):
        app = webtest.TestApp(debug_app,
                                relative_to=os.path.dirname(__file__))
        data = app.encode_multipart(
            [], [('file', 'html%s404.html' % os.sep)])
        self.assertIn(to_bytes('404.html'), data[-1])

    def test_encode_multipart(self):
        data = self.app.encode_multipart(
            [], [('file', 'data.txt', b'data')])
        self.assertIn(to_bytes('data.txt'), data[-1])

        data = self.app.encode_multipart(
            [], [(b'file', b'data.txt', b'data')])
        self.assertIn(to_bytes('data.txt'), data[-1])

        data = self.app.encode_multipart(
            [('key', 'value')], [])
        self.assertIn(to_bytes('name="key"'), data[-1])

        data = self.app.encode_multipart(
            [(b'key', b'value')], [])
        self.assertIn(to_bytes('name="key"'), data[-1])

    def test_encode_multipart_content_type(self):
        data = self.app.encode_multipart(
            [], [('file', 'data.txt', b'data',
                 'text/x-custom-mime-type')])
        self.assertIn(to_bytes('Content-Type: text/x-custom-mime-type'),
                      data[-1])

        data = self.app.encode_multipart(
            [('file', webtest.Upload('data.txt', b'data',
                                     'text/x-custom-mime-type'))], [])
        self.assertIn(to_bytes('Content-Type: text/x-custom-mime-type'),
                      data[-1])

    def test_get_params(self):
        resp = self.app.get('/', 'a=b')
        resp.mustcontain('a=b')
        resp = self.app.get('/?a=b', dict(c='d'))
        resp.mustcontain('a=b', 'c=d')
        resp = self.app.get('/?a=b&c=d', dict(e='f'))
        resp.mustcontain('a=b', 'c=d', 'e=f')

    def test_request_with_testrequest(self):
        req = webtest.TestRequest.blank('/')
        resp = self.app.request(req, method='POST')
        resp.charset = 'ascii'
        assert 'REQUEST_METHOD: POST' in resp.text

    def test_patch(self):
        resp = self.app.patch('/')
        self.assertIn('PATCH', resp)

        resp = self.app.patch('/', xhr=True)
        self.assertIn('PATCH', resp)

    def test_custom_headers(self):
        resp = self.app.post('/', headers={'Accept': 'text/plain'})
        resp.charset = 'ascii'
        assert 'HTTP_ACCEPT: text/plain' in resp.text


class TestStatus(unittest.TestCase):

    def setUp(self):
        self.app = webtest.TestApp(debug_app)

    def check_status(self, status, awaiting_status=None):
        resp = Response()
        resp.request = Request.blank('/')
        resp.status = status
        return self.app._check_status(awaiting_status, resp)

    def test_check_status_asterisk(self):
        self.assertEqual(self.check_status('200 Ok', '*'), None)

    def test_check_status_almost_asterisk(self):
        self.assertEqual(self.check_status('200 Ok', '2*'), None)

    def test_check_status_tuple(self):
        self.assertEqual(self.check_status('200 Ok', (200,)), None)
        self.assertRaises(webtest.AppError,
                          self.check_status, '200 Ok', (400,))

    def test_check_status_none(self):
        self.assertEqual(self.check_status('200 Ok', None), None)
        self.assertRaises(webtest.AppError, self.check_status, '400 Ok')

    def test_check_status_with_custom_reason(self):
        self.assertEqual(self.check_status('200 Ok', '200 Ok'), None)
        self.assertRaises(webtest.AppError,
                          self.check_status, '200 Ok', '200 Good Response')
        self.assertRaises(webtest.AppError,
                          self.check_status, '200 Ok', '400 Bad Request')


class TestParserFeature(unittest.TestCase):

    def test_parser_features(self):
        app = webtest.TestApp(debug_app, parser_features='custom')
        self.assertEqual(app.RequestClass.ResponseClass.parser_features,
                         'custom')


class TestAppError(unittest.TestCase):

    def test_app_error(self):
        resp = Response(to_bytes('blah'))
        err = webtest.AppError('message %s', resp)
        self.assertEqual(err.args, ('message blah',))

    def test_app_error_with_bytes_message(self):
        resp = Response('\xe9'.encode('utf8'))
        resp.charset = 'utf8'
        err = webtest.AppError(to_bytes('message %s'), resp)
        self.assertEqual(err.args, ('message \xe9',))

    def test_app_error_with_unicode(self):
        err = webtest.AppError('messag\xe9 %s', '\xe9')
        self.assertEqual(err.args, ('messag\xe9 \xe9',))

    def test_app_error_misc(self):
        resp = Response('\xe9'.encode('utf8'))
        resp.charset = ''
        # dont check the output. just make sure it doesn't fail
        webtest.AppError(to_bytes('message %s'), resp)
        webtest.AppError('messag\xe9 %s', b'\xe9')


class TestPasteVariables(unittest.TestCase):

    def call_FUT(self, **kwargs):
        def application(environ, start_response):
            resp = Response()
            environ['paste.testing_variables'].update(kwargs)
            return resp(environ, start_response)
        return webtest.TestApp(application)

    def test_paste_testing_variables_raises(self):
        app = self.call_FUT(body='1')
        req = Request.blank('/')
        self.assertRaises(ValueError, app.do_request, req, '*', False)

    def test_paste_testing_variables(self):
        app = self.call_FUT(check='1')
        req = Request.blank('/')
        resp = app.do_request(req, '*', False)
        self.assertEqual(resp.check, '1')


class TestCookies(unittest.TestCase):

    def test_supports_providing_cookiejar(self):
        cookiejar = http_cookiejar.CookieJar()
        app = webtest.TestApp(debug_app, cookiejar=cookiejar)
        self.assertIs(cookiejar, app.cookiejar)

    def test_set_cookie(self):
        def cookie_app(environ, start_response):
            req = Request(environ)
            self.assertEqual(req.cookies['foo'], 'bar')
            self.assertEqual(req.cookies['fizz'], ';bar=baz')

            status = to_bytes("200 OK")
            body = ''
            headers = [
                ('Content-Type', 'text/html'),
                ('Content-Length', str(len(body))),
            ]
            start_response(status, headers)
            return [to_bytes(body)]

        app = webtest.TestApp(cookie_app)
        app.set_cookie('foo', 'bar')
        app.set_cookie('fizz', ';bar=baz')  # Make sure we're escaping.
        app.get('/')
        app.reset()

        app = webtest.TestApp(cookie_app,
                              extra_environ={'HTTP_HOST': 'testserver'})
        app.set_cookie('foo', 'bar')
        app.set_cookie('fizz', ';bar=baz')  # Make sure we're escaping.
        app.get('/')
        app.reset()

    def test_preserves_cookies(self):
        def cookie_app(environ, start_response):
            req = Request(environ)
            status = "200 OK"
            body = '<html><body><a href="/go/">go</a></body></html>'
            headers = [
                ('Content-Type', 'text/html'),
                ('Content-Length', str(len(body))),
            ]
            if req.path_info != '/go/':
                headers.extend([
                    ('Set-Cookie', 'spam=eggs'),
                    ('Set-Cookie', 'foo=bar;baz'),
                ])
            else:
                self.assertEqual(dict(req.cookies),
                                  {'spam': 'eggs', 'foo': 'bar'})
                self.assertIn('foo=bar', environ['HTTP_COOKIE'])
                self.assertIn('spam=eggs', environ['HTTP_COOKIE'])
            start_response(status, headers)
            return [to_bytes(body)]

        app = webtest.TestApp(cookie_app)
        self.assertTrue(not app.cookiejar,
                        'App should initially contain no cookies')

        self.assertFalse(app.cookies)
        res = app.get('/')
        self.assertEqual(app.cookies['spam'], 'eggs')
        self.assertEqual(app.cookies['foo'], 'bar')
        res = res.click('go')
        self.assertEqual(app.cookies['spam'], 'eggs')
        self.assertEqual(app.cookies['foo'], 'bar')

        app.reset()
        self.assertFalse(bool(app.cookies))

    def test_secure_cookies(self):
        def cookie_app(environ, start_response):
            req = Request(environ)
            status = "200 OK"
            body = '<html><body><a href="/go/">go</a></body></html>'
            headers = [
                ('Content-Type', 'text/html'),
                ('Content-Length', str(len(body))),
            ]
            if req.path_info != '/go/':
                headers.extend([
                    ('Set-Cookie', 'spam=eggs; secure'),
                    ('Set-Cookie', 'foo=bar;baz; secure'),
                ])
            else:
                self.assertEqual(dict(req.cookies),
                                  {'spam': 'eggs', 'foo': 'bar'})
                self.assertIn('foo=bar', environ['HTTP_COOKIE'])
                self.assertIn('spam=eggs', environ['HTTP_COOKIE'])
            start_response(status, headers)
            return [to_bytes(body)]

        app = webtest.TestApp(cookie_app)

        self.assertFalse(app.cookies)
        res = app.get('https://localhost/')
        self.assertEqual(app.cookies['spam'], 'eggs')
        self.assertEqual(app.cookies['foo'], 'bar')
        res = res.click('go')
        self.assertEqual(app.cookies['spam'], 'eggs')
        self.assertEqual(app.cookies['foo'], 'bar')

    def test_cookies_readonly(self):
        app = webtest.TestApp(debug_app)
        try:
            app.cookies = {}
        except:
            pass
        else:
            self.fail('testapp.cookies should be read-only')

    @mock.patch('http.cookiejar.time.time')
    def test_expires_cookies(self, mock_time):
        def cookie_app(environ, start_response):
            status = to_bytes("200 OK")
            body = ''
            headers = [
                ('Content-Type', 'text/html'),
                ('Content-Length', str(len(body))),
                ('Set-Cookie',
                 'spam=eggs; Expires=Tue, 21-Feb-2013 17:45:00 GMT;'),
            ]
            start_response(status, headers)
            return [to_bytes(body)]
        app = webtest.TestApp(cookie_app)
        self.assertTrue(not app.cookiejar,
                        'App should initially contain no cookies')

        mock_time.return_value = 1361464946.0
        app.get('/')
        self.assertTrue(app.cookies, 'Response should have set cookies')

        mock_time.return_value = 1461464946.0
        app.get('/')
        self.assertFalse(app.cookies, 'Response should have unset cookies')

    def test_http_cookie(self):
        def cookie_app(environ, start_response):
            req = Request(environ)
            status = to_bytes("200 OK")
            body = 'Cookie.'
            assert dict(req.cookies) == {'spam': 'eggs'}
            assert environ['HTTP_COOKIE'] == 'spam=eggs'
            headers = [
                ('Content-Type', 'text/html'),
                ('Content-Length', str(len(body))),
            ]
            start_response(status, headers)
            return [to_bytes(body)]

        app = webtest.TestApp(cookie_app)
        self.assertTrue(not app.cookies,
                        'App should initially contain no cookies')

        res = app.get('/', headers=[('Cookie', 'spam=eggs')])
        self.assertFalse(app.cookies,
                         'Response should not have set cookies')
        self.assertEqual(res.request.environ['HTTP_COOKIE'], 'spam=eggs')
        self.assertEqual(dict(res.request.cookies), {'spam': 'eggs'})

    def test_http_localhost_cookie(self):
        def cookie_app(environ, start_response):
            status = to_bytes("200 OK")
            body = 'Cookie.'
            headers = [
                ('Content-Type', 'text/html'),
                ('Content-Length', str(len(body))),
                ('Set-Cookie',
                 'spam=eggs; Domain=localhost;'),
            ]
            start_response(status, headers)
            return [to_bytes(body)]

        app = webtest.TestApp(cookie_app)
        self.assertTrue(not app.cookies,
                        'App should initially contain no cookies')

        res = app.get('/')
        res = app.get('/')
        self.assertTrue(app.cookies,
                        'Response should not have set cookies')
        self.assertEqual(res.request.environ['HTTP_COOKIE'], 'spam=eggs')
        self.assertEqual(dict(res.request.cookies), {'spam': 'eggs'})

    def test_cookie_policy(self):

        def cookie_app(environ, start_response):
            status = to_bytes("200 OK")
            body = 'Cookie.'
            headers = [
                ('Content-Type', 'text/plain'),
                ('Content-Length', str(len(body))),
                ('Set-Cookie',
                 'spam=eggs; secure; Domain=.example.org;'),
            ]
            start_response(status, headers)
            return [to_bytes(body)]

        policy = webtest.app.CookiePolicy()
        flags = (
            policy.DomainStrictNoDots |
            policy.DomainRFC2965Match |
            policy.DomainStrictNonDomain)
        policy.strict_ns_domain |= flags
        cookiejar = http_cookiejar.CookieJar(policy=policy)
        app = webtest.TestApp(
            cookie_app,
            cookiejar=cookiejar,
            extra_environ={'HTTP_HOST': 'example.org'})
        res = app.get('/')
        res = app.get('/')
        self.assertFalse(app.cookies,
                        'Response should not have set cookies')
        self.assertNotIn('HTTP_COOKIE', res.request.environ)
        self.assertEqual(dict(res.request.cookies), {})


class TestEnviron(unittest.TestCase):

    def test_get_extra_environ(self):
        app = webtest.TestApp(debug_app,
                              extra_environ={'HTTP_ACCEPT_LANGUAGE': 'ru',
                                             'foo': 'bar'})
        res = app.get('http://localhost/')
        self.assertIn('HTTP_ACCEPT_LANGUAGE: ru', res, res)
        self.assertIn("foo: 'bar'", res, res)

        res = app.get('http://localhost/', extra_environ={'foo': 'baz'})
        self.assertIn('HTTP_ACCEPT_LANGUAGE: ru', res, res)
        self.assertIn("foo: 'baz'", res, res)

    def test_post_extra_environ(self):
        app = webtest.TestApp(debug_app,
                              extra_environ={'HTTP_ACCEPT_LANGUAGE': 'ru',
                                             'foo': 'bar'})
        res = app.post('http://localhost/')
        self.assertIn('HTTP_ACCEPT_LANGUAGE: ru', res, res)
        self.assertIn("foo: 'bar'", res, res)

        res = app.post('http://localhost/', extra_environ={'foo': 'baz'})
        self.assertIn('HTTP_ACCEPT_LANGUAGE: ru', res, res)
        self.assertIn("foo: 'baz'", res, res)

    def test_request_extra_environ(self):
        app = webtest.TestApp(debug_app,
                              extra_environ={'HTTP_ACCEPT_LANGUAGE': 'ru',
                                             'foo': 'bar'})
        res = app.request('http://localhost/', method='GET')
        self.assertIn('HTTP_ACCEPT_LANGUAGE: ru', res, res)
        self.assertIn("foo: 'bar'", res, res)

        res = app.request('http://localhost/', method='GET',
                          environ={'foo': 'baz'})
        self.assertIn('HTTP_ACCEPT_LANGUAGE: ru', res, res)
        self.assertIn("foo: 'baz'", res, res)


deform_upload_fields_text = """
      <input type="hidden" name="_charset_" />
      <input type="hidden" name="__formid__" value="deform"/>
      <input type="text" name="title" value="" id="deformField1"/>
      <input type="hidden" name="__start__" value="fileupload:mapping"/>
        <input type="file" name="fileupload" id="deformField2"/>
      <input type="hidden" name="__end__" value="fileupload:mapping"/>
      <textarea id="deformField3" name="description" rows="10" cols="60">
      </textarea>
      <button
          id="deformSubmit"
          name="Submit"
          type="submit"
          value="Submit">
          Submit
      </button>
"""


def get_submit_app(form_id, form_fields_text):
    def submit_app(environ, start_response):
        req = Request(environ)
        status = "200 OK"
        if req.method == "GET":
            body = """
<html>
  <head><title>form page</title></head>
  <body>
    <form
        id="%s"
        action=""
        method="POST"
        enctype="multipart/form-data"
        accept-charset="utf-8">

      %s
    </form>
  </body>
</html>
""" % (form_id, form_fields_text)
        else:
            body_head = """
<html>
    <head><title>display page</title></head>
    <body>
"""

            body_parts = []
            for (name, value) in req.POST.items():
                if hasattr(value, 'filename'):
                    body_parts.append("%s:%s:%s\n" % (
                        name,
                        value.filename,
                        value.value.decode('ascii')))
                else:
                    body_parts.append("%s:%s\n" % (
                        name, value))

            body_foot = """    </body>
    </html>
    """
            body = body_head + "".join(body_parts) + body_foot
        if not isinstance(body, bytes):
            body = body.encode('utf8')
        headers = [
            ('Content-Type', 'text/html; charset=utf-8'),
            ('Content-Length', str(len(body)))]
        start_response(status, headers)
        return [body]
    return submit_app


class TestFieldOrder(unittest.TestCase):

    def test_submit_with_file_upload(self):
        uploaded_file_name = 'test.txt'
        uploaded_file_contents = to_bytes('test content file upload')

        deform_upload_file_app = get_submit_app('deform',
                                                deform_upload_fields_text)
        app = webtest.TestApp(deform_upload_file_app)
        res = app.get('/')
        self.assertEqual(res.status_int, 200)
        self.assertEqual(
            res.headers['content-type'], 'text/html; charset=utf-8')
        self.assertEqual(res.content_type, 'text/html')
        self.assertEqual(res.charset, 'utf-8')

        single_form = res.forms["deform"]
        single_form.set("title", "testtitle")
        single_form.set("fileupload",
                        (uploaded_file_name, uploaded_file_contents))
        single_form.set("description", "testdescription")
        display = single_form.submit("Submit")
        self.assertIn("""
_charset_:
__formid__:deform
title:testtitle
__start__:fileupload:mapping
fileupload:test.txt:test content file upload
__end__:fileupload:mapping
description:testdescription
Submit:Submit
""".strip(), display, display)

    def test_post_with_file_upload(self):
        uploaded_file_name = 'test.txt'
        uploaded_file_contents = to_bytes('test content file upload')

        deform_upload_file_app = get_submit_app('deform',
                                                deform_upload_fields_text)
        app = webtest.TestApp(deform_upload_file_app)
        display = app.post("/", OrderedDict([
            ('_charset_', ''),
            ('__formid__', 'deform'),
            ('title', 'testtitle'),
            ('__start__', 'fileupload:mapping'),
            ('fileupload', webtest.Upload(uploaded_file_name,
                                          uploaded_file_contents)),
            ('__end__', 'fileupload:mapping'),
            ('description', 'testdescription'),
            ('Submit', 'Submit')]))

        self.assertIn("""
_charset_:
__formid__:deform
title:testtitle
__start__:fileupload:mapping
fileupload:test.txt:test content file upload
__end__:fileupload:mapping
description:testdescription
Submit:Submit""".strip(), display, display)

    def test_field_order_is_across_all_fields(self):
        fields = """
<input type="text" name="letter" value="a">
<input type="text" name="letter" value="b">
<input type="text" name="number" value="1">
<input type="text" name="letter" value="c">
<input type="text" name="number" value="2">
<input type="submit" name="save" value="Save 1">
<input type="text" name="letter" value="d">
<input type="submit" name="save" value="Save 2">
<input type="text" name="letter" value="e">
"""
        submit_app = get_submit_app('test', fields)
        app = webtest.TestApp(submit_app)
        get_res = app.get("/")
        # Submit the form with the second submit button.
        display = get_res.forms[0].submit('save', 1)
        self.assertIn("""
letter:a
letter:b
number:1
letter:c
number:2
letter:d
save:Save 2
letter:e""".strip(), display, display)


class TestFragments(unittest.TestCase):

    def test_url_without_fragments(self):
        app = webtest.TestApp(debug_app)
        res = app.get('http://localhost/')
        self.assertEqual(res.status_int, 200)

    def test_url_with_fragments(self):
        app = webtest.TestApp(debug_app)
        res = app.get('http://localhost/#ananchor')
        self.assertEqual(res.status_int, 200)


def application(environ, start_response):
    req = Request(environ)
    if req.path_info == '/redirect':
        req.path_info = '/path'
        resp = Response()
        resp.status = '302 Found'
        resp.location = req.path
    else:
        resp = Response()
        resp.body = to_bytes(
            '<html><body><a href="%s">link</a></body></html>' % req.path)
    return resp(environ, start_response)


class TestScriptName(unittest.TestCase):

    def test_script_name(self):
        app = webtest.TestApp(application)

        resp = app.get('/script', extra_environ={'SCRIPT_NAME': '/script'})
        resp.mustcontain('href="/script"')

        resp = app.get('/script/redirect',
                       extra_environ={'SCRIPT_NAME': '/script'})
        self.assertEqual(resp.status_int, 302)
        self.assertEqual(resp.location,
                         'http://localhost/script/path',
                         resp.location)

        resp = resp.follow(extra_environ={'SCRIPT_NAME': '/script'})
        resp.mustcontain('href="/script/path"')
        resp = resp.click('link')
        resp.mustcontain('href="/script/path"')

    def test_app_script_name(self):
        app = webtest.TestApp(application,
                              extra_environ={'SCRIPT_NAME': '/script'})
        resp = app.get('/script/redirect')
        self.assertEqual(resp.status_int, 302)
        self.assertEqual(resp.location,
                         'http://localhost/script/path',
                         resp.location)

        resp = resp.follow()
        resp.mustcontain('href="/script/path"')
        resp = resp.click('link')
        resp.mustcontain('href="/script/path"')

    def test_script_name_doesnt_match(self):
        app = webtest.TestApp(application)
        resp = app.get('/path', extra_environ={'SCRIPT_NAME': '/script'})
        resp.mustcontain('href="/script/path"')


class TestWSGIProxy(unittest.TestCase):

    def setUp(self):
        self.s = http.StopableWSGIServer.create(debug_app)
        self.s.wait()

    def test_proxy_with_url(self):
        app = webtest.TestApp(self.s.application_url)
        resp = app.get('/')
        self.assertEqual(resp.status_int, 200)

    def test_proxy_with_environ(self):
        def app(environ, start_response):
            pass
        os.environ['WEBTEST_TARGET_URL'] = self.s.application_url
        app = webtest.TestApp(app)
        del os.environ['WEBTEST_TARGET_URL']
        resp = app.get('/')
        self.assertEqual(resp.status_int, 200)

    def tearDown(self):
        self.s.shutdown()


class TestAppXhrParam(unittest.TestCase):

    def setUp(self):
        self.app = webtest.TestApp(debug_app)

    def test_xhr_param_change_headers(self):
        app = self.app
        # FIXME: this test isn`t work for head request
        # now I don't know how to test head request
        functions = (app.get, app.post, app.delete,
                     app.put, app.options)  # app.head
        for func in functions:
            resp = func('/', xhr=True)
            resp.charset = 'ascii'
            self.assertIn('HTTP_X_REQUESTED_WITH: XMLHttpRequest',
                          resp.text)


class TestRequest(unittest.TestCase):

    def test_pytest_collection_disabled(self):
        self.assertFalse(webtest.TestRequest.__test__)
