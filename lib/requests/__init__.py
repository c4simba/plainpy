"""requests for plainpy: HTTP for humans, in the interpreter and in compiled programs (plainpy
--compile), https over plainpy's ssl (OpenSSL 3 on Linux and macOS, mbedtls.obj on KolibriOS).

    import requests

    r = requests.get("https://api.github.com/repos/psf/requests", timeout=10)
    r.raise_for_status()
    info: dict[str, int] = ...                      # compiled code: r.json() gives what it is assigned to
    print(r.status_code, r.headers["content-type"], r.json()["stargazers_count"])

    with requests.Session() as s:
        s.headers["Authorization"] = "Bearer ..."
        s.post("https://httpbin.org/post", json={"a": 1}, timeout=5)

The API of requests 2.32: get / post / put / patch / delete / head / options / request, Session,
Response (status_code, ok, headers, content, text, json(), cookies, history, iter_content,
iter_lines, raise_for_status), params, data (forms), json, files (multipart), headers, cookies,
auth (Basic), timeout, allow_redirects, stream, verify (False, a CA file), cert, response hooks,
gzip / deflate bodies, redirections, keep-alive connections, requests' exceptions.

Not here: proxies (ProxyError), Digest authentication, netrc, IDNA host names, Brotli / zstd.
Compiled programs: r.json() needs the type of its result (x: dict[str, int] = r.json()), a dict's
values one type ({"page": "2"}, not {"page": 2, "q": "x"}), PreparedRequest.body is bytes; the
classes with two bases in requests have one there (see requests.exceptions)."""
from .utils import VERSION as __version__
from . import utils, structures, cookies, auth, adapters, exceptions, status_codes
from .models import PreparedRequest, Request, Response
from .api import delete, get, head, options, patch, post, put, request
from .sessions import Session, session
from .status_codes import codes
from .exceptions import (ConnectionError, ConnectTimeout, FileModeWarning, HTTPError, JSONDecodeError, ReadTimeout,
                         RequestException, Timeout, TooManyRedirects, URLRequired)

__title__ = "requests"
__description__ = "Python HTTP for Humans."
__url__ = "https://requests.readthedocs.io"
__author__ = "Kenneth Reitz"
__license__ = "Apache-2.0"
