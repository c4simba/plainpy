"""requests.get(url), post(url, data=..., json=...), ...: one request each, in a Session of its own."""
from _ppy_typing import TypeVar
from .models import Response
from .sessions import Session

_P = TypeVar("_P")
_D = TypeVar("_D")
_H = TypeVar("_H")
_C = TypeVar("_C")
_F = TypeVar("_F")
_A = TypeVar("_A")
_T = TypeVar("_T")
_V = TypeVar("_V")
_E = TypeVar("_E")
_J = TypeVar("_J")
_X = TypeVar("_X")
_K = TypeVar("_K")


def request(method: str, url: str, params: _P = None, data: _D = None, headers: _H = None, cookies: _C = None,
            files: _F = None, auth: _A = None, timeout: _T = None, allow_redirects: bool = True, proxies: _X = None,
            hooks: _K = None, stream: bool | None = None, verify: _V = None, cert: _E = None, json: _J = None) -> Response:
    """The response to method url.

    params: the query (a dict, a list of pairs, a str); data: the body (a dict / list of pairs: a
    form, a str, bytes, a file); json: the body as JSON; headers: a dict; cookies: a dict or a
    RequestsCookieJar; files: multipart files ({"name": content or (filename, content[, type])});
    auth: (user, password) or an AuthBase; timeout: seconds or (connect, read); allow_redirects;
    stream: the body read later; verify: False, or a file / folder of certificate authorities;
    cert: a client certificate (a file, or (cert, key))."""
    with Session() as session:
        return session.request(method, url, params, data, headers, cookies, files, auth, timeout, allow_redirects,
                               proxies, hooks, stream, verify, cert, json)


def get(url: str, params: _P = None, *, data: _D = None, headers: _H = None, cookies: _C = None, files: _F = None,
        auth: _A = None, timeout: _T = None, allow_redirects: bool = True, proxies: _X = None, hooks: _K = None,
        stream: bool | None = None, verify: _V = None, cert: _E = None, json: _J = None) -> Response:
    """A GET request (params: the query)."""
    return request("GET", url, params, data, headers, cookies, files, auth, timeout, allow_redirects, proxies, hooks, stream, verify, cert, json)


def options(url: str, *, params: _P = None, data: _D = None, headers: _H = None, cookies: _C = None, files: _F = None,
            auth: _A = None, timeout: _T = None, allow_redirects: bool = True, proxies: _X = None, hooks: _K = None,
            stream: bool | None = None, verify: _V = None, cert: _E = None, json: _J = None) -> Response:
    """An OPTIONS request."""
    return request("OPTIONS", url, params, data, headers, cookies, files, auth, timeout, allow_redirects, proxies, hooks, stream, verify, cert, json)


def head(url: str, *, params: _P = None, data: _D = None, headers: _H = None, cookies: _C = None, files: _F = None,
         auth: _A = None, timeout: _T = None, allow_redirects: bool = False, proxies: _X = None, hooks: _K = None,
         stream: bool | None = None, verify: _V = None, cert: _E = None, json: _J = None) -> Response:
    """A HEAD request (redirections not followed unless allow_redirects=True)."""
    return request("HEAD", url, params, data, headers, cookies, files, auth, timeout, allow_redirects, proxies, hooks, stream, verify, cert, json)


def post(url: str, data: _D = None, json: _J = None, *, params: _P = None, headers: _H = None, cookies: _C = None,
         files: _F = None, auth: _A = None, timeout: _T = None, allow_redirects: bool = True, proxies: _X = None,
         hooks: _K = None, stream: bool | None = None, verify: _V = None, cert: _E = None) -> Response:
    """A POST request (data: a form, a str, bytes; json: a value sent as JSON)."""
    return request("POST", url, params, data, headers, cookies, files, auth, timeout, allow_redirects, proxies, hooks, stream, verify, cert, json)


def put(url: str, data: _D = None, *, params: _P = None, headers: _H = None, cookies: _C = None, files: _F = None,
        auth: _A = None, timeout: _T = None, allow_redirects: bool = True, proxies: _X = None, hooks: _K = None,
        stream: bool | None = None, verify: _V = None, cert: _E = None, json: _J = None) -> Response:
    """A PUT request."""
    return request("PUT", url, params, data, headers, cookies, files, auth, timeout, allow_redirects, proxies, hooks, stream, verify, cert, json)


def patch(url: str, data: _D = None, *, params: _P = None, headers: _H = None, cookies: _C = None, files: _F = None,
          auth: _A = None, timeout: _T = None, allow_redirects: bool = True, proxies: _X = None, hooks: _K = None,
          stream: bool | None = None, verify: _V = None, cert: _E = None, json: _J = None) -> Response:
    """A PATCH request."""
    return request("PATCH", url, params, data, headers, cookies, files, auth, timeout, allow_redirects, proxies, hooks, stream, verify, cert, json)


def delete(url: str, *, params: _P = None, data: _D = None, headers: _H = None, cookies: _C = None, files: _F = None,
           auth: _A = None, timeout: _T = None, allow_redirects: bool = True, proxies: _X = None, hooks: _K = None,
           stream: bool | None = None, verify: _V = None, cert: _E = None, json: _J = None) -> Response:
    """A DELETE request."""
    return request("DELETE", url, params, data, headers, cookies, files, auth, timeout, allow_redirects, proxies, hooks, stream, verify, cert, json)
