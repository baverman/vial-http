import json
import time

from vial import vfunc, vim
from vial.utils import focus_window
from vial.helpers import echoerr
from vial.widgets import make_scratch
from vial.compat import PY2, iteritems, bstr

if PY2:
    import urllib
    import httplib
    import Cookie
    from cStringIO import StringIO
else:
    from http import cookies as Cookie
    from http import client as httplib
    from urllib import parse as urllib
    from io import BytesIO as StringIO

from .util import (get_headers_and_templates, send_collector, prepare_request,
                   PrepareException, render_template, Headers, pretty_xml,
                   get_connection_settings)

CONNECT_TIMEOUT = 5
READ_TIMEOUT = 30
XML_FORMAT_SIZE_THRESHOLD = 2 ** 20


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


def http():
    lines = vim.current.buffer[:]
    line, _ = vim.current.window.cursor
    line -= 1

    headers, templates = get_headers_and_templates(lines, line)
    pwd_func = lambda p: vfunc.inputsecret('{}: '.format(p))
    input_func = lambda p: vfunc.input('{}: '.format(p))
    try:
        method, url, query, body, tlist, rend = prepare_request(lines, line, headers, input_func, pwd_func)
    except PrepareException as e:
        echoerr(str(e))
        return

    connect_timeout = float(headers.pop('Vial-Connect-Timeout', CONNECT_TIMEOUT))
    read_timeout = float(headers.pop('Vial-Timeout', READ_TIMEOUT))

    (host, port), u = get_connection_settings(url, headers)
    headers.set('Host', u.netloc)

    path = u.path
    if u.query:
        path += '?' + u.query

    if query:
        path += ('&' if u.query else '?') + urllib.urlencode(query)

    certfile = headers.pop('Vial-Client-Cert')
    keyfile = headers.pop('Vial-Client-Key')

    if u.scheme == 'https':
        import ssl
        ctx = ssl._create_unverified_context(certfile=certfile, keyfile=keyfile)
        cn = httplib.HTTPSConnection(host, port or 443,
                                     timeout=connect_timeout, context=ctx)
    else:
        cn = httplib.HTTPConnection(host, port or 80, timeout=connect_timeout)

    cn = send_collector(cn)

    start = time.time()
    cn.connect()
    ctime = int((time.time() - start) * 1000)

    cn.sock.settimeout(read_timeout)

    cn.request(method, path, body, headers)
    response = cn.getresponse()
    rtime = int((time.time() - start) * 1000)

    cwin = vim.current.window

    win, buf = make_scratch('__vial_http_req__', title='Request')
    buf[:] = cn._sdata.splitlines()
    win.cursor = 1, 0

    win, buf = make_scratch('__vial_http_hdr__', title='Response headers')
    if PY2:
        buf[:] = [r.rstrip('\r\n') for r in response.msg.headers]
    else:
        buf[:] = ['{}: {}'.format(*r).encode('utf-8') for r in response.msg._headers]

    win.cursor = 1, 0

    content = response.read()
    size = len(content)

    win, buf = make_scratch('__vial_http_raw__', title='Raw Response')
    buf[:] = content.splitlines()
    win.cursor = 1, 0

    if PY2:
        rcontent_type = response.msg.gettype()
    else:
        rcontent_type = response.msg.get_content_type()

    content, ctype, jdata = format_content(rcontent_type, content)

    win, buf = make_scratch('__vial_http__')
    win.options['statusline'] = 'Response: {} {} {}ms {}ms {}'.format(
        response.status, response.reason, ctime, rtime, sizeof_fmt(size))
    vim.command('set filetype={}'.format(ctype))
    buf[:] = content.splitlines(False)
    win.cursor = 1, 0

    focus_window(cwin)

    cj = Cookie.SimpleCookie()
    if PY2:
        cheaders = response.msg.getheaders('set-cookie')
    else:
        cheaders = response.msg.get_all('set-cookie')
    for h in cheaders or []:
        cj.load(h)
    rcookies = {k: v.value for k, v in iteritems(cj)}
    cookies = {k: v.coded_value for k, v in iteritems(cj)}

    def set_cookies(*args):
        args = args or sorted(cookies.keys())
        return 'Cookie: ' + ';'.join('{}={}'.format(k, cookies[k]) for k in args)

    ctx = {'body': content, 'json': jdata,
           'headers': Headers(response.getheaders()),
           'cookies': cookies,
           'rcookies': rcookies,
           'set_cookies': set_cookies}

    for t in tlist:
        if t in templates:
            lines = render_template(templates[t], **ctx).splitlines()
        else:
            lines = ['ERROR: template {} not found'.format(t)]
        vfunc.append(rend + 1, [''] + lines)
        rend += 1 + len(lines)


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
