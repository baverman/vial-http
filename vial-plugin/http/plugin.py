import json
import time
import urllib
import httplib
import urlparse
import Cookie

from vial import vfunc, vim
from vial.utils import focus_window
from vial.helpers import echoerr
from vial.widgets import make_scratch

from .util import (get_headers_and_templates, send_collector, prepare_request, PrepareException,
                   render_template, Headers)

CONNECT_TIMEOUT = 5
READ_TIMEOUT = 30


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

    u = urlparse.urlsplit(url)
    if not u.hostname:
        host = headers.pop('host', '')
        if not host.startswith('http://') and not host.startswith('https://'):
            host = 'http://' + host
        u = urlparse.urlsplit(host + url)

    if u.query:
        query = urlparse.parse_qsl(u.query, True) + query

    path = u.path
    if query:
        path += '?' + urllib.urlencode(query)

    if u.scheme == 'https':
        import ssl
        cn = httplib.HTTPSConnection(u.hostname, u.port or 443,
                                     timeout=CONNECT_TIMEOUT,
                                     context=ssl._create_unverified_context())
    else:
        cn = httplib.HTTPConnection(u.hostname, u.port or 80,
                                    timeout=CONNECT_TIMEOUT)

    cn = send_collector(cn)

    start = time.time()
    cn.connect()
    ctime = int((time.time() - start) * 1000)

    cn.sock.settimeout(READ_TIMEOUT)

    cn.request(method, path, body, headers)
    response = cn.getresponse()
    rtime = int((time.time() - start) * 1000)

    cwin = vim.current.window

    win, buf = make_scratch('__vial_http_req__', title='Request')
    buf[:] = cn._sdata.splitlines()
    win.cursor = 1, 0

    win, buf = make_scratch('__vial_http_hdr__', title='Response headers')
    buf[:] = [r.rstrip('\r\n') for r in response.msg.headers]
    win.cursor = 1, 0

    content = response.read()
    try:
        jdata = json.loads(content)
        content = json.dumps(jdata, ensure_ascii=False, sort_keys=True, indent=2)
        ctype = 'json'
    except ValueError:
        ctype = 'html'
        jdata = {}

    win, buf = make_scratch('__vial_http__')
    win.options['statusline'] = 'Response: {} {} {}ms {}ms'.format(
        response.status, response.reason, ctime, rtime)
    vim.command('set filetype={}'.format(ctype))
    buf[:] = content.splitlines(False)
    win.cursor = 1, 0

    focus_window(cwin)

    cj = Cookie.SimpleCookie()
    for h in response.msg.getheaders('set-cookie'):
        cj.load(h)
    rcookies = {k: v.value for k, v in cj.items()}
    cookies = {k: v.coded_value for k, v in cj.items()}

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
    return 'Authorization: Basic ' + '{}:{}'.format(user, password).encode('base64').strip()


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
