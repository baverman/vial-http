from textwrap import dedent

from .util import (parse_request_line, render_template, get_headers_and_templates,
                   find_request)


def fill(param):
    return '!{}'.format(param)


def test_parse_request_line():
    result = parse_request_line('GET /query')
    assert result['method'] == 'GET'
    assert result['url'] == '/query'

    assert parse_request_line('GET /query?some_arg')['url'] == '/query?some_arg'

    result = parse_request_line('GET /query q=value f:=value mp@=value H:value')
    assert result['url'] == '/query'
    assert result['query'] == [('q', 'value')]
    assert result['form'] == [('f', 'value')]
    assert result['files'] == [('mp', 'value')]
    assert result['headers'] == {'H': 'value'}

    result = parse_request_line('GET /query q=value < body')
    assert result['query'] == [('q', 'value')]
    assert result['body_from_file'] == 'body'

    result = parse_request_line('GET /query q=__pwd__', pwd_func=fill)
    assert result['query'] == [('q', '!q')]

    result = parse_request_line('GET /query q=__input__', input_func=fill)
    assert result['query'] == [('q', '!q')]

    assert parse_request_line('GET /query | tpl1, tpl2')['templates'] == ['tpl1', 'tpl2']

    result = parse_request_line('GET /query < /file | tpl1')
    assert result['body_from_file'] == '/file'
    assert result['templates'] == ['tpl1']


def test_render_template():
    assert render_template('${body}', body='foo') == 'foo'
    assert render_template('Token: ${json["token"]}', json={"token": "foo"}) == "Token: foo"
    assert render_template('Token: ${json["token"]}', json={}) == "Token: None"
    assert render_template('Token: ${json[token]}', json={}) == "ERROR: name 'token' is not defined"


def test_get_templates():
    content = dedent('''\
        TEMPLATE boo
        foo: foo

        TEMPLATE foo
        bar
        baz

        TEMPLATE baz << HERE
        baz

        baz
        HERE

        boo: boo
        foo
    ''')
    lines = content.splitlines()
    h, t = get_headers_and_templates(lines, len(lines) - 1)
    assert t == {'foo': 'bar\nbaz', 'boo': 'foo: foo', 'baz': 'baz\n\nbaz'}
    assert h.headers == [('User-Agent', 'vial-http'), ('boo', 'boo')]


def test_find_request():
    content = dedent('''\
        POST /uri1

        POST /uri2

        POST /uri3
        boo

        POST /uri4
        boo
        foo

        POST /uri5 << HERE
        boo
        HERE
    ''')

    lines = content.splitlines()

    assert find_request(lines, 0) == ('POST /uri1', None, 0)
    assert find_request(lines, 1) == ('POST /uri1', None, 0)

    assert find_request(lines, 2) == ('POST /uri2', None, 2)
    assert find_request(lines, 3) == ('POST /uri2', None, 2)

    assert find_request(lines, 4) == ('POST /uri3', 'boo', 5)
    assert find_request(lines, 5) == ('POST /uri3', 'boo', 5)
    assert find_request(lines, 6) == ('POST /uri3', 'boo', 5)

    assert find_request(lines, 7) == ('POST /uri4', 'boo\nfoo', 9)
    assert find_request(lines, 8) == ('POST /uri4', 'boo\nfoo', 9)
    assert find_request(lines, 9) == ('POST /uri4', 'boo\nfoo', 9)
    assert find_request(lines, 10) == ('POST /uri4', 'boo\nfoo', 9)

    assert find_request(lines, 11) == ('POST /uri5', 'boo', 13)
    assert find_request(lines, 12) == ('POST /uri5', 'boo', 13)
    assert find_request(lines, 13) == ('POST /uri5', 'boo', 13)
