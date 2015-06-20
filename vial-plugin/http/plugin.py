import httplib
import json
import re
import time
import urllib
import urlparse

from vial import vfunc, vim
from vial.utils import focus_window
from vial.widgets import make_scratch

header_regex = re.compile(r'^[-\w\d]+$')
value_regex = re.compile(r'^([-_\w\d]+)(:=|=|:)(.+)$')


def get_headers(lines, line):
    headers = {}
    for l in lines[:line]:
        try:
            header, value = l.split(':', 1)
        except ValueError:
            continue

        if header_regex.match(header):
            headers[header.lower()] = value.strip()

    return headers


def get_request(lines, line):
    parts = lines[line].split()
    method = parts[0]
    url = parts[1]
    query = []
    form = []
    headers = {}
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
                headers[param.lower()] = value
            elif op == ':=':
                form.append((param, value))

    if form:
        body = urllib.urlencode(form)
        headers['content-type'] = 'application/x-www-form-urlencoded'

    if not form:
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
                    headers['content-type'] = 'application/json'
            except ValueError:
                pass

    return method, url, headers, query, body


def http():
    lines = vim.current.buffer[:]
    line, _ = vim.current.window.cursor
    line -= 1

    headers = get_headers(lines, line)
    method, url, qheaders, query, body = get_request(lines, line)
    headers.update(qheaders)

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
        cn = httplib.HTTPSConnection(u.hostname, u.port or 443)
    else:
        cn = httplib.HTTPConnection(u.hostname, u.port or 80)

    start = time.time()
    cn.connect()
    ctime = int((time.time() - start) * 1000)

    cn.request(method, path, body, headers)
    response = cn.getresponse()
    rtime = int((time.time() - start) * 1000)

    cwin = vim.current.window
    win, buf = make_scratch('__vial_http__')
    win.options['statusline'] = 'vial-http: {} {} {}ms {}ms'.format(
        response.status, response.reason, rtime, ctime)

    content = response.read()
    try:
        jdata = json.loads(content)
        content = json.dumps(jdata, ensure_ascii=False, sort_keys=True, indent=2)
        vim.command('setfiletype json')
    except ValueError:
        vim.command('setfiletype html')

    buf[:] = content.splitlines()
    win.cursor = 1, 0
    focus_window(cwin)
