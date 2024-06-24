import json
import time

try:
    from shlex import quote as cmd_quote
except ImportError:
    from pipes import quote as cmd_quote

from vial import vfunc, vim
from vial.utils import focus_window
from vial.helpers import echoerr
from vial.widgets import make_scratch
from vial.compat import PY2, iteritems, bstr

if PY2:
    import urllib
    import urlparse
    import httplib
    from cStringIO import StringIO
else:
    from http import client as httplib
    from urllib import parse as urllib
    from urllib import parse as urlparse
    from io import BytesIO as StringIO

from .util import (get_headers_and_templates, send_collector, prepare_request,
                   PrepareException, render_template, Headers, pretty_xml,
                   get_connection_settings, CookieJar)

CONNECT_TIMEOUT = 5
READ_TIMEOUT = 30
XML_FORMAT_SIZE_THRESHOLD = 2 ** 20

http_response = ''


def set_http_response(response):
    global http_response
    http_response = response
    return http_response;


def get_http_response():
    return http_response


def sizeof_fmt(num, suffix='b'):
    for unit in ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
        if abs(num) < 1024.0:
            if not unit:
                return "%d%s%s" % (num, unit, suffix)
            else:
                return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)


def format_json(content):
    try:
        jdata = json.loads(content)
    except:
        jdata = {}
    else:
        content = json.dumps(jdata, ensure_ascii=False, sort_keys=True, indent=2)

    return content, 'json', jdata


def format_xml(content):
    if len(content) < XML_FORMAT_SIZE_THRESHOLD:
        buf = StringIO()
        try:
            pretty_xml(content, buf)
        except:
            pass
        else:
            content = buf.getvalue()
    return content, 'xml', {}


def format_content(content_type, content):
    if content_type == 'application/json':
        return format_json(content)
    elif content_type == 'text/html':
        return content, 'html', {}
    elif content_type in ('application/xml', 'text/xml', 'text/plain') or content_type.endswith('+xml'):
        return format_xml(content)

    return content, 'text', {}


class RequestContext(object):
    def _request(self, method, url, query, body, headers):
        (host, port), u = get_connection_settings(url, headers)
        headers.set('Host', u.netloc)

        path = u.path
        if u.query:
            path += '?' + u.query

        if query:
            path += ('&' if u.query else '?') + urllib.urlencode(query)

        if u.scheme == 'https':
            import ssl
            ctx = ssl._create_unverified_context(certfile=self.certfile,
                                                 keyfile=self.keyfile)
            cn = httplib.HTTPSConnection(host, port or 443,
                                         timeout=self.connect_timeout, context=ctx)
        else:
            cn = httplib.HTTPConnection(host, port or 80,
                                        timeout=self.connect_timeout)


        cn = send_collector(cn)

        start = time.time()
        cn.connect()
        self.ctime = int((time.time() - start) * 1000)

        cn.sock.settimeout(self.read_timeout)

        cn.request(method, path, body, headers)
        self.response = cn.getresponse()
        self.rtime = int((time.time() - start) * 1000)

        self.content = self.response.read()
        self.ftime = int((time.time() - start) * 1000)
        self.response.close()
        cn.close()

        self.response.request = ((host, port),
                                 '{}://{}{}'.format(u.scheme, u.netloc, path or '/'))

        self.cj = CookieJar()
        self.cj.load(self.response)

        self.raw_request = cn._sdata
        return self.response

    def request(self, method, url, query, body, headers):
        self.connect_timeout = float(headers.pop('Vial-Connect-Timeout', CONNECT_TIMEOUT))
        self.read_timeout = float(headers.pop('Vial-Timeout', READ_TIMEOUT))
        self.certfile = headers.pop('Vial-Client-Cert')
        self.keyfile = headers.pop('Vial-Client-Key')
        self.history = []

        do_redirects = headers.pop('Vial-Redirect', '').lower() in ('1', 't', 'true', 'yes')
        original_headers = headers

        for _ in range(5):
            resp = self._request(method, url, query, body, headers)
            self.history.append(resp)

            if not do_redirects or resp.status not in (301, 302, 303):
                break

            url = resp.getheader('location')
            if not url:
                break

            u = urlparse.urlsplit(url)
            if u.netloc == headers.get('Host'):
                headers = original_headers
            else:
                headers = original_headers.copy('User-Agent')

    @property
    def rcookies(self):
        return {k: v.value for k, v in iteritems(self.cj.cookies)}

    @property
    def cookies(self):
        return {k: v.coded_value for k, v in iteritems(self.cj.cookies)}


def parse_request_at_cursor():
    lines = vim.current.buffer[:]
    line, _ = vim.current.window.cursor
    line -= 1

    headers, templates = get_headers_and_templates(lines, line)
    pwd_func = lambda p: vfunc.inputsecret('{}: '.format(p))
    input_func = lambda p: vfunc.input('{}: '.format(p))
    return (headers, templates) + prepare_request(lines, line, headers, input_func, pwd_func)


def http():
    try:
        headers, templates, method, url, query, body, tlist, rend = parse_request_at_cursor()
    except PrepareException as e:
        echoerr(str(e))
        return

    rctx = RequestContext()
    rctx.request(method, url, query, body, headers)

    cwin = vim.current.window

    win, buf = make_scratch('__vial_http_req__', title='Request')
    rlines = rctx.raw_request.splitlines()

    hlines = []
    for r in rctx.history[:-1]:
        hlines.append(bstr('Redirect {} from {}'.format(
            r.status, r.request[1]), 'utf-8'))
    if hlines:
        hlines.append(b'----------------')

    buf[:] = hlines + rlines
    win.cursor = 1, 0

    win, buf = make_scratch('__vial_http_hdr__', title='Response headers')
    if PY2:
        buf[:] = [r.rstrip('\r\n') for r in rctx.response.msg.headers]
    else:
        buf[:] = ['{}: {}'.format(*r).encode('utf-8') for r in rctx.response.msg._headers]

    win.cursor = 1, 0

    size = len(rctx.content)

    win, buf = make_scratch('__vial_http_raw__', title='Raw Response')
    buf[:] = rctx.content.splitlines()
    win.cursor = 1, 0

    if PY2:
        rcontent_type = rctx.response.msg.gettype()
    else:
        rcontent_type = rctx.response.msg.get_content_type()

    content, ctype, jdata = format_content(rcontent_type, rctx.content)

    win, buf = make_scratch('__vial_http__')
    response_text = 'Response: {} {} {}ms {}ms {}'.format(
        rctx.response.status, rctx.response.reason,
        rctx.ctime, rctx.rtime, sizeof_fmt(size))
    win.options['statusline'] = set_http_response(response_text)
    vim.command('set filetype={}'.format(ctype))
    buf[:] = content.splitlines(False)
    win.cursor = 1, 0

    focus_window(cwin)

    def set_cookies(*args):
        cookies = rctx.cookies
        args = args or sorted(cookies.keys())
        return 'Cookie: ' + ';'.join('{}={}'.format(k, cookies[k]) for k in args)

    ctx = {'body': content, 'json': jdata,
           'headers': Headers(rctx.response.getheaders()),
           'cookies': rctx.cookies,
           'rcookies': rctx.rcookies,
           'set_cookies': set_cookies}

    for t in tlist:
        if t in templates:
            lines = render_template(templates[t], **ctx).splitlines()
        else:
            lines = ['ERROR: template {} not found'.format(t)]
        vfunc.append(rend + 1, [''] + lines)
        rend += 1 + len(lines)


def curl():
    try:
        headers, _, method, url, query, body, tlist, _ = parse_request_at_cursor()
    except PrepareException as e:
        echoerr(str(e))
        return

    vial_host = headers.pop('Vial-Curl-Host', None)
    opts = headers.pop('Vial-Curl-Opts', None)

    if vial_host:
        headers.set('Host', vial_host)

    (host, port), u = get_connection_settings(url, headers)
    # headers.set('Host', u.netloc)
    path = u.path
    if u.query:
        path += '?' + u.query

    if query:
        path += ('&' if u.query else '?') + urllib.urlencode(query)

    cmd = ['curl']
    if method != 'GET':
        cmd.extend(['-X', method])

    if opts:
        cmd.append(opts)

    ignored_headers = {it.strip().lower() for it in headers.pop('vial-curl-ignored-headers', '').split(',')}
    if headers.get('User-Agent') == 'vial-http':
        ignored_headers.add('user-agent')

    form = None
    if body and headers.get('Content-Type') == 'application/x-www-form-urlencoded':
        headers.pop('Content-Type')
        form = urlparse.parse_qsl(body)
        body = None

    for k, v in headers.items():
        if k.lower() not in ignored_headers:
            cmd.extend(['-H', cmd_quote(k + ': ' + v)])

    if form:
        for k, v in form:
            cmd.extend(['-d', '{}={}'.format(k, urllib.quote_plus(v))])

    if body:
        cmd.extend(['--data-binary', '@-'])

    cmd.append(cmd_quote(u._replace(path=path).geturl()))

    if body:
        cmd.extend(['<< EOF\n' + body + '\nEOF'])

    content = ' '.join(cmd)

    cwin = vim.current.window
    win, buf = make_scratch('__vial_http_curl_')
    buf[:] = content.splitlines(False)
    win.cursor = 1, 0
    focus_window(cwin)


def basic_auth(user, password):
    from base64 import b64encode
    return b'Authorization: Basic ' + b64encode(b'%s:%s' % (bstr(user), bstr(password)))


def basic_auth_func():
    user = vfunc.input('Username: ')
    if not user:
        return
    password = vfunc.inputsecret('Password: ')
    return basic_auth(user, password)


def basic_auth_cmd(user=None):
    if not user:
        user = vfunc.input('Username: ')
    if not user:
        return
    password = vfunc.inputsecret('Password: ')
    vfunc.append(vfunc.line('.'), basic_auth(user, password))
