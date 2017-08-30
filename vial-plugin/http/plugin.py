import os.path
import httplib
import json
import re
import time
import urllib
import urlparse
import shlex

from vial import vfunc, vim
from vial.utils import focus_window
from vial.widgets import make_scratch
from .multipart import encode_multipart

header_regex = re.compile(r'^\+?[-\w\d]+$')
value_regex = re.compile(r'^([-_\w\d]+)(:=|@=|=|:)(.+)$')


def send_collector(connection):
    connection._sdata = ''
    oldsend = connection.send
    def send(data):
        connection._sdata += data
        return oldsend(data)
    connection.send = send
    return connection


class Headers(object):
    def __init__(self):
        self.headers = [('User-Agent', 'vial-http')]

    def set(self, header, value):
        self.headers = [r for r in self.headers if r[0].lower() != header.lower()]
        self.headers.append((header, value))

    def update(self, headers):
        for k, v in headers.items():
            self.set(k, v)

    def add(self, header, value):
        self.headers.append((header, value))

    def __contains__(self, header):
        return any(h.lower() == header.lower() for h, _ in self.headers)

    def pop(self, header, default=None):
        result = default
        headers = []
        for h, v in self.headers:
            if h.lower() == header.lower():
                result = v
            else:
                headers.append((h, v))
        self.headers = headers
        return result

    def iteritems(self):
        return self.headers

    def __iter__(self):
        return (h for h, _ in self.headers)


def get_headers(lines, line):
    headers = Headers()
    for l in lines[:line]:
        try:
            header, value = l.split(':', 1)
        except ValueError:
            continue

        if header_regex.match(header):
            if header[0] == '+':
                headers.add(header[1:], value.strip())
            else:
                headers.set(header, value.strip())

    return headers


def get_request(lines, line, headers):
    parts = shlex.split(lines[line], True)
    method = parts[0]
    url = parts[1]
    query = []
    form = []
    files = []
    body = None
    for p in parts[2:]:
        m = value_regex.match(p)
        if m:
            param, op, value = m.group(1, 2, 3)
            if value == '__pwd__':
                value = vfunc.inputsecret('{}: '.format(param))
            if op == '=':
                query.append((param, value))
            elif op == ':':
                headers.set(param, value)
            elif op == ':=':
                form.append((param, value))
            elif op == '@=':
                fname = os.path.basename(value)
                with open(value, 'rb') as f:
                    content = f.read()
                files.append((param, {'filename': fname, 'content': content}))

    content_type_is_set = False
    if not content_type_is_set and files:
        body, h = encode_multipart(form, files)
        headers.update(h)
        content_type_is_set = True

    if not content_type_is_set and form:
        body = urllib.urlencode(form)
        headers.set('Content-Type', 'application/x-www-form-urlencoded')
        content_type_is_set = True

    if not content_type_is_set:
        bodylines = []
        for l in lines[line+1:]:
            if not l:
                break
            bodylines.append(l)

        if bodylines:
            body = '\n'.join(bodylines)
            try:
                json.loads(body)
                if 'content-type' not in headers:
                    headers.set('Content-Type', 'application/json')
            except ValueError:
                pass

    return method, url, query, body


def http():
    lines = vim.current.buffer[:]
    line, _ = vim.current.window.cursor
    line -= 1

    headers = get_headers(lines, line)
    method, url, query, body = get_request(lines, line, headers)

    host = headers.pop('host', '')
    u = urlparse.urlsplit(url)
    if not u.hostname:
        u = urlparse.urlsplit(host + url)

    if u.query:
        query = urlparse.parse_qsl(u.query, True) + query

    path = u.path
    if query:
        path += '?' + urllib.urlencode(query)

    if u.scheme == 'https':
        import ssl
        cn = httplib.HTTPSConnection(u.hostname, u.port or 443, context=ssl._create_unverified_context())
    else:
        cn = httplib.HTTPConnection(u.hostname, u.port or 80)

    cn = send_collector(cn)

    start = time.time()
    cn.connect()
    ctime = int((time.time() - start) * 1000)

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

    win, buf = make_scratch('__vial_http__')
    win.options['statusline'] = 'Response: {} {} {}ms {}ms'.format(
        response.status, response.reason, rtime, ctime)
    vim.command('set filetype={}'.format(ctype))
    buf[:] = content.splitlines()
    win.cursor = 1, 0

    focus_window(cwin)


def basic_auth():
    user = vfunc.input('Username: ')
    if not user:
        return
    password = vfunc.inputsecret('Password: ')
    return 'Authorization: Basic ' + '{}:{}'.format(user, password).encode('base64')
