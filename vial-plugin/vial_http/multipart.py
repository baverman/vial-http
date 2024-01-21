import mimetypes
import random
import string

from vial.compat import bstr

_BOUNDARY_CHARS = string.digits + string.ascii_letters


def encode_multipart(fields, files, boundary=None):
    r"""Encode dict of form fields and dict of files as multipart/form-data.
    Return tuple of (body_string, headers_dict). Each value in files is a dict
    with required keys 'filename' and 'content', and optional 'mimetype' (if
    not specified, tries to guess mime type or uses 'application/octet-stream').

    >>> body, headers = encode_multipart({'FIELD': 'VALUE'},
    ...                                  {'FILE': {'filename': 'F.TXT', 'content': 'CONTENT'}},
    ...                                  boundary='BOUNDARY')
    >>> print('\n'.join(repr(l) for l in body.split('\r\n')))
    '--BOUNDARY'
    'Content-Disposition: form-data; name="FIELD"'
    ''
    'VALUE'
    '--BOUNDARY'
    'Content-Disposition: form-data; name="FILE"; filename="F.TXT"'
    'Content-Type: text/plain'
    ''
    'CONTENT'
    '--BOUNDARY--'
    ''
    >>> print(sorted(headers.items()))
    [('Content-Length', '193'), ('Content-Type', 'multipart/form-data; boundary=BOUNDARY')]
    >>> len(body)
    193
    """
    def escape_quote(s):
        return bstr(s).replace(b'"', b'\\"')

    if boundary is None:
        boundary = ''.join(random.choice(_BOUNDARY_CHARS) for i in range(30)).encode('latin1')
    lines = []

    for name, value in fields:
        lines.extend((
            b'--%s' % boundary,
            b'Content-Disposition: form-data; name="%s"' % escape_quote(name),
            b'',
            bstr(value, 'utf-8'),
        ))

    for name, value in files:
        filename = value['filename']
        if 'mimetype' in value:
            mimetype = value['mimetype']
        else:
            mimetype = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
        lines.extend((
            b'--%s' % boundary,
            b'Content-Disposition: form-data; name="%s"; filename="%s"' % (
                    escape_quote(name), escape_quote(filename)),
            b'Content-Type: %s' % (bstr(mimetype)),
            b'',
            value['content'],
        ))

    lines.extend((
        b'--%s--' % boundary,
        b'',
    ))
    body = b'\r\n'.join(lines)

    headers = {
        'Content-Type': b'multipart/form-data; boundary=%s' % boundary,
        'Content-Length': bstr(str(len(body))),
    }

    return (body, headers)
