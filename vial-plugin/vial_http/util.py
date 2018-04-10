import os.path
import re
import shlex
import json

from xml.etree import cElementTree as etree

from vial.compat import PY2, bstr, filter, sstr, ustr

if PY2:
    import urllib
    import urlparse
    import Cookie
    from cStringIO import StringIO
else:
    from urllib import parse as urllib
    from urllib import parse as urlparse
    from http import cookies as Cookie
    from io import BytesIO as StringIO

from .multipart import encode_multipart

header_regex = re.compile(r'^\+?[-\w\d]+$')
value_regex = re.compile(r'^([-_\w\d]+)(:=|@=|=|:)(.+)$')


class PrepareException(Exception): pass


def get_line(content, pos):
    return content.count('\n', 0, pos)


def get_heredocs(lines):
    ball = '\n'.join(lines)
    result = []
    hds = re.finditer(r'(?sm)(\s+<<\s+(\w+))$\n(.+?)(\2)', ball)
    for m in hds:
        ss = m.start(1)
        start = get_line(ball, m.start(2))
        end = get_line(ball, m.start(4))
        body = m.group(3)
        if body and body[-1] == '\n':
            body = body[:-1]
        result.append((start, end, ball[:ss].splitlines()[start], body))

    return result


def find_request(lines, line):
    for s, e, l, body in get_heredocs(lines):
        if s <= line <= e:
            return l, body, e

    l = line
    while l > 0:
        lcontent = lines[l-1]
        if not lcontent.strip() or lcontent[0] == '#':
            break
        l -= 1
        if l <= 0:
            break

    line = l

    bodylines = []
    for l in lines[line+1:]:
        if not l.strip():
            break
        bodylines.append(l)

    return lines[line], '\n'.join(bodylines) or None, line + len(bodylines)


def parse_request_line(line, input_func=None, pwd_func=None):
    line = line.rstrip()

    query = []
    form = []
    files = []
    headers = {}
    result = {'query': query, 'form': form, 'files': files, 'headers': headers}

    rparts = line.split(None, 2)
    if len(rparts) < 2:
        return None

    result['method'], result['url'] = rparts[0], rparts[1]
    if len(rparts) > 2:
        tail = rparts[2]
    else:
        tail = ''

    if tail:
        parts = shlex.split(tail, True)
        try:
            pos = parts.index('|')
        except ValueError:
            pass
        else:
            result['templates'] = filter(None, (r.strip() for r in ''.join(parts[pos+1:]).split(',')))
            parts = parts[:pos]

        if len(parts) >= 2:
            if parts[-2] == '<':
                result['body_from_file'] = parts[-1]
                parts = parts[:-2]

        for p in parts:
            m = value_regex.match(p)
            if m:
                param, op, value = m.group(1, 2, 3)

                if value == '__pwd__' and pwd_func:
                    value = pwd_func(param)

                if value == '__input__' and input_func:
                    value = input_func(param)

                if op == '=':
                    query.append((param, value))
                elif op == ':':
                    headers[param] = value
                elif op == ':=':
                    form.append((param, value))
                elif op == '@=':
                    files.append((param, value))

    return result


def prepare_request(lines, line, headers, input_func=None, pwd_func=None):
    rline, body, rend  = find_request(lines, line)
    raw = parse_request_line(rline, input_func, pwd_func)
    if not raw:
        raise PrepareException('Invalid format: METHOD uri [qs_param=value] [form_param:=value] [file_param@=value] '
                               '[Header:value] [< /filename-with-body] [| tpl1,tpl2] [<< HEREDOC]')

    headers.update(raw['headers'])

    if body is None and 'body_from_file' in raw:
        try:
            with open(raw['body_from_file']) as f:
                body = f.read()
        except Exception as e:
            raise PrepareException('Can\'t open body file {}: {}'.format(raw['body_from_file'], e))

    if (body and 'content-type' not in headers
            and (body[:1000].lstrip() or ' ')[0] in '{['):
        try:
            json.loads(body)
        except ValueError:
            pass
        else:
            headers.set('Content-Type', 'application/json')

    if body is None and (raw['files'] or headers.get('Content-Type') == 'multipart/form-data'):
        files = []
        for k, v in raw['files']:
            fname = os.path.basename(v)
            try:
                with open(v, 'rb') as f:
                    content = f.read()
            except Exception as e:
                raise PrepareException('Error opening file param {}: {}'.format(v, e))
            files.append((k, {'filename': fname, 'content': content}))
        body, h = encode_multipart(raw['form'], files)
        headers.update(h)

    if body is None and raw['form']:
        body = urllib.urlencode(raw['form'])
        headers.set('Content-Type', 'application/x-www-form-urlencoded')

    return raw['method'], raw['url'], raw['query'], body, raw.get('templates', []), rend


def send_collector(connection):
    connection._sdata = b''
    oldsend = connection.send
    def send(data):
        if len(connection._sdata) <= 65536:
            connection._sdata += data
            if len(connection._sdata) > 65536:
                connection._sdata += b'\n...TRUNCATED...'
        return oldsend(data)
    connection.send = send
    return connection


class Headers(object):
    def __init__(self, headers=None):
        self.headers = headers or [('User-Agent', 'vial-http')]

    def set(self, header, value):
        self.headers = [r for r in self.headers if r[0].lower() != header.lower()]
        self.headers.append((header, value))

    def get(self, name, default=None):
        try:
            return self[name]
        except KeyError:
            return default

    def __getitem__(self, name):
        result = [r[1] for r in self.headers if r[0].lower() == name.lower()]
        if not result:
            raise KeyError(name)
        return result[0]

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

    def items(self):
        return self.headers

    def __iter__(self):
        return (h for h, _ in self.headers)

    def copy(self, *names):
        result = Headers()
        for name in names:
            v = self.get(name)
            if v is not None:
                result.set(name, v)
        return result


def get_headers_and_templates(lines, line):
    headers = Headers()
    templates = {}
    it = iter(lines[:line])
    while True:
        l = next(it, None)
        if l is None:
            break

        if l.startswith('TEMPLATE '):
            name, sep, here = l[len('TEMPLATE '):].strip().partition('<<')
            name = name.strip()
            here = here.strip()

            tlines = []
            while True:
                l = next(it, None)
                if l is None:
                    break

                if sep:
                    pos = l.find(here)
                    if pos == 0:
                        break
                    elif pos > 0:
                        tlines.append(l[:pos])
                        break
                elif not l.strip():
                    break
                tlines.append(l)
            templates[name] ='\n'.join(tlines)
        else:
            try:
                header, value = l.split(':', 1)
            except ValueError:
                continue

            if header_regex.match(header):
                if header[0] == '+':
                    headers.add(header[1:], value.strip())
                else:
                    headers.set(header, value.strip())

    return headers, templates


def render_template(template, **ctx):
    def sub(match):
        try:
            return eval(match.group(1), ctx, ctx)
        except KeyError:
            return "None"
    try:
        return re.sub(r'\$\{(.+?)\}', sub, template)
    except Exception as e:
        return 'ERROR: {}'.format(e)


def pretty_xml(text, out, ident='  '):
    from xml.sax.saxutils import quoteattr, escape
    from collections import Counter

    ns_aliases = {}
    ns_cache = {}
    ns_cnt = Counter()
    def get_alias(tag):
        try:
            return ns_cache[tag]
        except KeyError:
            pass

        pos = tag.find('}')
        if pos < 0:
            result = tag
        else:
            rtag = tag[pos+1:]
            prefix = ns_aliases[tag[1:pos]]
            result = '{}:{}'.format(prefix, rtag) if prefix else rtag

        ns_cache[tag] = result
        return result

    buf = StringIO(text)
    for (event, elem) in etree.iterparse(buf, ('start-ns',)):
        alias = elem[0]
        if alias in ns_cnt:
            if not alias:
                alias = 'ns'

            falias = alias
            while falias in ns_cnt:
                ns_cnt[alias] += 1
                falias = '{}{}'.format(alias, ns_cnt[alias])
            alias = falias

        ns_aliases[elem[1]] = alias

    def _render(elem, level, first, use_level):
        tag = get_alias(elem.tag)
        attrib = ['{}={}'.format(get_alias(k), sstr(quoteattr(v), 'utf-8'))
                  for k, v in sorted(elem.attrib.items())]
        attrib = ustr((' ' + ' '.join(attrib)) if attrib else '', 'utf-8')
        if first:
            ns = ' ' + ' '.join('xmlns{}={}'.format((':' + v) if v else v, quoteattr(k))
                                for k, v in ns_aliases.items())
        else:
            ns = ''

        if use_level:
            nl = '\n' + ident * level
        else:
            nl = ''

        txt = elem.text
        txt = escape(txt) if txt and txt.strip() else ''

        tail = txt
        has_children = False
        for child in elem:
            if not has_children:
                out.write(u'{}<{}{}{}>{}'.format(nl, tag, ns, attrib, txt).encode('utf-8'))
            has_children = True
            _render(child, level+1, False, not tail)
            tail = child.tail
            tail = escape(txt) if tail and tail.strip() else ''
            if tail:
                out.write(bstr(tail, 'utf-8'))

        if has_children:
            if not tail:
                nl = '\n' + ident * level
            else:
                nl = ''

            out.write(u'{}</{}>'.format(nl, tag, txt).encode('utf-8'))
        else:
            if txt:
                out.write(u'{}<{}{}{}>{}</{}>'.format(nl, tag, ns, attrib, txt, tag).encode('utf-8'))
            else:
                out.write(u'{}<{}{}{}/>'.format(nl, tag, ns, attrib, txt).encode('utf-8'))

        return txt

    buf.seek(0)
    _render(etree.parse(buf).getroot(), 0, True, False)


def get_connection_settings(url, headers):
    u = urlparse.urlsplit(url)
    if not u.hostname:
        host = headers.pop('host', '')
        if not host.startswith('http://') and not host.startswith('https://'):
            host = 'http://' + host
        u = urlparse.urlsplit(host + url)

    vconnect = headers.pop('vial-connect', None)
    if vconnect:
        if not vconnect.startswith('http://') and not vconnect.startswith('https://'):
            vconnect = 'http://' + vconnect
        vu = urlparse.urlsplit(vconnect)
        return (vu.hostname, vu.port), u._replace(scheme=vu.scheme)

    return (u.hostname, u.port), u


class CookieJar(object):
    def __init__(self):
        self.cookies = Cookie.SimpleCookie()

    def load(self, response):
        if PY2:
            cheaders = response.msg.getheaders('set-cookie')
        else:
            cheaders = response.msg.get_all('set-cookie')
        for h in cheaders or []:
            self.cookies.load(h)
