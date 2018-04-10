0.4dev
======

* [Break] renamed python package ``http`` -> ``vial_http`` to
  avoid conflict with python3 stdlib.

* [Feature] python3 support.

* [Feature] timeout control via special headers ``Vial-Timeout`` and
  ``Vial-Connect-Timeout``.

* [Feature] force ``Host`` header with explicit connection via ``Vial-Connect``
  special header.

* [Feature] client can pass client certificate via ``Vial-Client-Cert`` and
  ``Vial-Client-Key`` special headers.

* [Feature] auto redirects via ``Vial-Redirect`` special header.

* [Fix] override headers in query string.

* [Fix] unicode error in xml decoder.


0.3
===

* [Feature] response size in status line.

* [Feature] XML formatting.

* [Feature] raw response window (you can see unformatted html/json/html).

* [Fix] query string merge (requests like ``/url?wsdl`` are send as ``/url?wsdl=``).


0.2
===

* [Break] swap response/connect times in window status line, now it has more
  natural order: connect time and then response read time.

* [Feature] templates!!

* [Feature] added ``:VialHttpBasicAuth [username]`` command.

* [Feature] default mappings for request execution and response window cycle.

* [Feature] request body can be set via filename or heredoc.

* [Feature] __input__ placeholder.
