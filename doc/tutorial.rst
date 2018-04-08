Tutorial
========

Write requests in file with ``*.http`` extension and run a request
under a cursor with ``:VialHttp`` command (``<leader><cr>`` mapping by
default).

Basic syntax::

    # comment string

    Some-Header: value

    METHOD /some/url [query_param=value] [form_param:=value] [file_param@=/path/to/file] \
                     [Header:value] [< /path/to/body] [| template1,template2] [<< HEREDOC]

    TEMPLATE name [<< HEREDOC]
    Header: ${json['field']}
    Header: ${headers['header']}
    Cookie: cookie=${cookies['cookie']}
    ${set_cookies()}


.. contents:: Table of Contents


GET requests
------------

GET request::

    GET https://vial-http.appspot.com    # Comments can be on a request line too.

Response::

    {
      "result": "Hello"
    }

You can define default host and headers::

    Host: https://vial-http.appspot.com
    Accept-Language: en
    Cookie: foo=bar

    GET /headers

Response::

    {
      "cookies": {
        "foo": "bar"
      },
      "headers": {
        "Accept-Encoding": "identity",
        "Accept-Language": "en",
        "Cookie": "foo=bar",
        "Host": "vial-http.appspot.com",
        "User-Agent": "vial-http
      }
    }


Simple, huh? Header value will be in effect for all requests on any line after.

In a response window status line you can see a response code and
connect/read times. For example ``Response: 200 OK 42ms 10ms``.

You can pass query params as usual::

    GET /query?q=some%3Astring+with+spaces&page=1

But there is a special syntax. ``=`` defines query string params with proper
uri encoding::

    GET /query q="some:string with spaces" page=1

It uses shell-like rules to detect request parts.
For example space escape with backslash::

    GET /query q=some:string\ with\ spaces page=1

``:`` is used to define request specific headers::

    GET /query q=query User-Agent:evil-bot

Response::

    {
      "headers": {
        "Accept-Encoding": "identity",
        "Accept-Language": "en",
        "Cookie": "foo=bar",
        "Host": "vial-http.appspot.com",
        "User-Agent": "evil-bot
      },
      "page": 1,
      "result": "query"
    }


POST data
---------

You can attach request body by inserting content after request line::

    POST /body
    some body
    for request

Response::

    {
      "result": "some body\nfor request"
    }

Vial-Http gets body from a continuous block of text without empty lines after request line.
If you need to deal with empty strings you can use heredoc::

    POST /body << HERE

    some

    body
    HERE

Response::

    {
      "result": "\nsome\n\nbody"
    }

Also you can use a file content as a body::

    POST /body < /tmp/some.data


POST form
---------

Forms are passed as url-encoded body with ``application/x-www-form-urlencoded``
content type::

    POST /form Content-Type:application/x-www-form-urlencoded
    p1=boo&p2=10

Response::

    {
      "p1": "boo",
      "p2": 10
    }

But it looks ugly and Vial-Http has special syntax via ``:=`` operator::

    POST /form p1:=boo p2:=10


POST JSON
---------

Vial-Http detects json content automatically and sets proper Content-Type::

    POST /json
    {
        "p1": "boo",
        "p2": "10"
    }

Response::

    {
      "p1": "boo",
      "p2": 10
    }


POST multipart form
-------------------

You need to set proper content type::

    POST /multipart p1:=boo p2:=10 Content-Type:multipart/form-data

Raw request::

    POST /multipart HTTP/1.1
    Host: vial-http.appspot.com
    Accept-Encoding: identity
    User-Agent: vial-http
    Content-Length: 203
    Content-Type: multipart/form-data; boundary=qAJxpKjDkp45PkAaahA1ZY1bUULutI

    --qAJxpKjDkp45PkAaahA1ZY1bUULutI
    Content-Disposition: form-data; name="p1"

    boo
    --qAJxpKjDkp45PkAaahA1ZY1bUULutI
    Content-Disposition: form-data; name="p2"

    10
    --qAJxpKjDkp45PkAaahA1ZY1bUULutI--

Or to use ``@=`` operator to attach a file field::

    POST /multipart p1:=boo p2:=10 file@=/tmp/some.data

Raw request::

    POST /multipart HTTP/1.1
    Host: vial-http.appspot.com
    Accept-Encoding: identity
    User-Agent: vial-http
    Content-Length: 358
    Content-Type: multipart/form-data; boundary=dsW9yj9Tihf5S188PgmgrKpJc5KE4G

    --dsW9yj9Tihf5S188PgmgrKpJc5KE4G
    Content-Disposition: form-data; name="p1"

    boo
    --dsW9yj9Tihf5S188PgmgrKpJc5KE4G
    Content-Disposition: form-data; name="p2"

    10
    --dsW9yj9Tihf5S188PgmgrKpJc5KE4G
    Content-Disposition: form-data; name="file"; filename="some.data"
    Content-Type: application/octet-stream

    some
    data

    --dsW9yj9Tihf5S188PgmgrKpJc5KE4G--


Basic authorization
-------------------

There is a ``:VialHttpBasicAuth`` command to make an ``Authorization``
HTTP basic auth header::

    :VialHttpBasicAuth [username]

It will output proper header you can use::

    Authorization: Basic dXNlcjpwYXNz

    GET /auth/basic

Response::

    {
      "password": "pass",
      "user": "user"
    }


Sensitive data/parametric requests
----------------------------------

You may want to use the same request with different data
or do not want to keep sensitive data in a file. Vial-Http
provides ``__input__`` and ``__pwd__`` placeholders for that::

    POST /auth/email email:=__input__ password:=__pwd__

Now you can input email and password in native vim inputs.


Handle state via templates
--------------------------

It's a common case to use data from a previous response, some headers, cookies
or json fields. Vial-Http provides templates for that::

    TEMPLATE cookies
    ${set_cookies()}

    POST /auth/email email:=boo password:=foo | cookies # templates are specified after pipe

Following line will be generated after this POST::

    Cookie: auth=boo:foo

You can execute::

    GET /whoami

And get authorized response::

    {
      "user": "boo"
    }

You can use these expression in ``${}``:

* ``json["field"]["subfield"]`` access to json body
* ``headers["header"]`` access to headers
* ``cookies["cookie"]`` access to cookies with proper quoting
* ``rcookies["cookie"]`` access to cookies without quoting
* ``set_cookie()`` outputs whole Cookie header with all cookies
* ``set_cookie('cookie1', 'cookie2')`` outputs Cookie header with particular cookies

Also you can use templates to generate other requests::

    TEMPLATE order << HERE # multiline template with empty lines needs heredoc
    GET /order/status id=${json['id']}

    DELETE /order id=${json['id']}
    HERE

    POST /order | order

Response::

    {
      "id": "dcf43d11-14b4-4737-a575-b72b945d6254"
    }

And you get generated lines ready to executed::

    GET /order/status id=dcf43d11-14b4-4737-a575-b72b945d6254

    DELETE /order id=dcf43d11-14b4-4737-a575-b72b945d6254


Special headers
---------------

Timeouts
~~~~~~~~

* ``Vial-Timeout``: sets read timeout (default is 5s).
* ``Vial-Connect-Timeout``: sets connection timeout (default is 30s).
