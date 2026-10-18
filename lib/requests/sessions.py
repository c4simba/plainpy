"""Sessions: a Session keeps what goes with each of its requests (headers, cookies, auth, params,
verify, cert) and its connections; request() prepares a request, sends it, follows redirections.
Compiled programs: Session.auth is a (user, password) tuple, verify a bool, cert a str (a request's
auth=, verify=, cert= take what requests' do)."""
import sys
from urllib.parse import urlsplit, urljoin
from _ppy_typing import TypeVar
from .models import PreparedRequest, Response, Request, _encode_params, _pairs
from .structures import CaseInsensitiveDict
from .cookies import RequestsCookieJar, cookiejar_from_dict
from .auth import apply_auth, _basic_auth_str
from .adapters import HTTPAdapter
from .utils import default_headers, get_auth_from_url, requote_uri
from .exceptions import TooManyRedirects, InvalidSchema, ProxyError

DEFAULT_REDIRECT_LIMIT = 30

_P = TypeVar("_P")                      # params
_D = TypeVar("_D")                      # data
_H = TypeVar("_H")                      # headers
_C = TypeVar("_C")                      # cookies
_F = TypeVar("_F")                      # files
_A = TypeVar("_A")                      # auth
_T = TypeVar("_T")                      # timeout: seconds, (connect, read), None
_V = TypeVar("_V")                      # verify: True, False, a CA file / folder
_E = TypeVar("_E")                      # cert: a file, (cert, key)
_J = TypeVar("_J")                      # json
_X = TypeVar("_X")                      # proxies
_K = TypeVar("_K")                      # hooks
_S = TypeVar("_S")


def _seconds(v: _S = None) -> float | None:
    if v is None:
        return None
    else:
        return float(v)


def _timeouts(timeout: _T = None) -> tuple[float | None, float | None]:
    """(connect, read) of timeout."""
    if timeout is None:
        return (None, None)
    elif isinstance(timeout, tuple):
        return (_seconds(timeout[0]), _seconds(timeout[1]))
    else:
        t = float(timeout)
        return (t, t)


def _verify(verify: _V = None) -> str:
    """How certificates are checked: "1" the system's authorities, "0" not, else a file or folder of them."""
    if verify is None:
        return "1"
    elif isinstance(verify, bool):
        return "1" if verify else "0"
    elif isinstance(verify, str):
        return verify
    else:
        return "1"


def _cert(cert: _E = None) -> tuple[str, str]:
    if cert is None:
        return ("", "")
    elif isinstance(cert, str):
        return (cert, "")
    elif isinstance(cert, tuple):
        return (cert[0], cert[1])
    else:
        return ("", "")


def _keys(params: _P = None) -> list[str]:
    if params is None:
        return []
    elif isinstance(params, dict):
        return [str(k) for k in params]
    elif isinstance(params, list):
        return [str(kv[0]) for kv in params]
    else:
        return []


def _merge_headers(base: CaseInsensitiveDict, headers: _H = None) -> CaseInsensitiveDict:
    """A session's headers with a request's (a request's None: that header not sent)."""
    merged = base.copy()
    if headers is None:
        return merged
    elif isinstance(headers, CaseInsensitiveDict):
        for k, v in headers.items():
            merged[k] = v
    elif isinstance(headers, dict):
        for k in headers:
            v = headers[k]
            if v is None:
                merged.pop(k)
            else:
                merged[k] = v
    return merged


def _jar(base: RequestsCookieJar, cookies: _C = None) -> RequestsCookieJar:
    jar = base.copy()
    if cookies is None:
        return jar
    elif isinstance(cookies, RequestsCookieJar):
        jar.update(cookies)
    elif isinstance(cookies, dict):
        cookiejar_from_dict(cookies, jar)
    return jar


def _port(scheme: str, port: int | None) -> int:
    if port is not None:
        return port
    if scheme == "https":
        return 443
    if scheme == "http":
        return 80
    return -1


def should_strip_auth(old_url: str, new_url: str) -> bool:
    """Is Authorization dropped on a redirection from old_url to new_url (another host; another
    scheme or port, except http to https on the standard ports)?"""
    old = urlsplit(old_url)
    new = urlsplit(new_url)
    if old.hostname != new.hostname:
        return True
    op = old.port
    np = new.port
    if old.scheme == "http" and (op is None or op == 80) and new.scheme == "https" and (np is None or np == 443):
        return False
    if old.scheme == new.scheme and _port(old.scheme, op) == _port(new.scheme, np):
        return False
    return True


def _hooked(r: Response, hooks: _K = None) -> Response:
    """r through the "response" hooks (a function or a list of them; one giving back something: that)."""
    if hooks is None:
        return r
    elif isinstance(hooks, dict):
        for k in hooks:
            if k == "response":
                h = hooks[k]
                if isinstance(h, list):
                    for f in h:
                        got = f(r)
                        if got is not None:
                            r = got
                else:
                    got = h(r)
                    if got is not None:
                        r = got
    return r


class Session:
    """Requests sharing headers, cookies, auth, params, verify, cert - and connections:
    s.get(url), s.post(url, data=...), ...; with Session() as s: closes them at the end."""

    def __init__(self) -> None:
        self.headers = default_headers()
        self.auth: tuple[str, str] | None = None
        self.proxies: dict[str, str] = {}
        self.params: dict[str, str] = {}
        self.stream = False
        self.verify = True
        self.cert: str | None = None
        self.max_redirects = DEFAULT_REDIRECT_LIMIT
        self.trust_env = True
        self.cookies = RequestsCookieJar()
        self.adapters: dict[str, HTTPAdapter] = {}
        self.mount("https://", HTTPAdapter())
        self.mount("http://", HTTPAdapter())

    def __enter__(self) -> "Session":
        return self

    def __exit__(self, et, ev, tb) -> bool:
        self.close()
        return False

    def mount(self, prefix: str, adapter: HTTPAdapter) -> None:
        """adapter for the URLs starting with prefix (the longest prefix wins)."""
        self.adapters[prefix] = adapter

    def get_adapter(self, url: str) -> HTTPAdapter:
        best = ""
        low = url.lower()
        for prefix in self.adapters:
            if low.startswith(prefix.lower()) and len(prefix) > len(best):
                best = prefix
        if not best:
            raise InvalidSchema("No connection adapters were found for " + repr(url))
        return self.adapters[best]

    def close(self) -> None:
        """The connections closed."""
        for prefix in self.adapters:
            self.adapters[prefix].close()

    def _query(self, params: _P = None) -> str:
        """The session's params (not given again in params), then params, as a query string."""
        mine = _encode_params(params)
        if not self.params:
            return mine
        given = _keys(params)
        rest: list[tuple[str, str]] = []
        for k in self.params:
            if k not in given:
                rest.append((k, self.params[k]))
        theirs = _encode_params(rest)
        if theirs and mine:
            return theirs + "&" + mine
        return theirs or mine

    def _auth(self, p: PreparedRequest) -> PreparedRequest:
        """p with the session's auth, else the URL's user and password."""
        auth = self.auth
        if auth is not None:
            return apply_auth(p, auth)
        user, password = get_auth_from_url(p.url)
        if user or password:
            p.headers["Authorization"] = _basic_auth_str(user, password)
        return p

    def prepare_request(self, request: Request) -> PreparedRequest:
        """request's PreparedRequest with the session's headers, params, cookies and auth."""
        p = request.prepare()
        merged = self.headers.copy()
        for k, v in p.headers.items():
            merged[k] = v
        p.headers = merged
        if self.params:
            q = _encode_params(self.params)
            p.url = p.url + ("&" if "?" in p.url else "?") + q
        jar = self.cookies.copy()
        jar.update(p._cookies)
        p.prepare_cookies(jar)
        if not request.has_auth:
            p = self._auth(p)
        return p

    def request(self, method: str, url: str, params: _P = None, data: _D = None, headers: _H = None, cookies: _C = None,
                files: _F = None, auth: _A = None, timeout: _T = None, allow_redirects: bool = True, proxies: _X = None,
                hooks: _K = None, stream: bool | None = None, verify: _V = None, cert: _E = None, json: _J = None) -> Response:
        """The response to method url (the session's headers, params, cookies, auth with these)."""
        if proxies:
            raise ProxyError("proxies are not supported by plainpy's requests")
        p = PreparedRequest()
        p.prepare_method(method)
        p.prepare_url(url, self._query(params))
        p.prepare_headers(_merge_headers(self.headers, headers))
        p.prepare_cookies(_jar(self.cookies, cookies))
        p.prepare_body(data, files, json)
        if auth is not None:
            p = apply_auth(p, auth)
        else:
            p = self._auth(p)
        r = self.send(p, stream=stream, timeout=timeout, verify=verify, cert=cert, allow_redirects=allow_redirects)
        return _hooked(r, hooks)

    def send(self, request: PreparedRequest, stream: bool | None = None, timeout: _T = None, verify: _V = None,
             cert: _E = None, allow_redirects: bool = True, proxies: _X = None) -> Response:
        """The response to a PreparedRequest (redirections followed unless allow_redirects is False)."""
        if proxies:
            raise ProxyError("proxies are not supported by plainpy's requests")
        streamed = self.stream if stream is None else stream
        connect_t, read_t = _timeouts(timeout)
        check = _verify(self.verify) if verify is None else _verify(verify)
        cert_file, key_file = _cert(self.cert) if cert is None else _cert(cert)
        r = self.get_adapter(request.url).send(request, streamed, connect_t, read_t, check, cert_file, key_file)
        self.cookies.extract(r._set_cookies, r._cookie_host, r._cookie_path)
        if not allow_redirects:
            return r
        history: list[Response] = []
        prev = request
        while r.is_redirect:
            if len(history) >= self.max_redirects:
                raise TooManyRedirects("Exceeded " + str(self.max_redirects) + " redirects.", response=r)
            r.history = list(history)
            history.append(r)
            r.content
            r.close()
            new = self._redirected(r, prev)
            r = self.get_adapter(new.url).send(new, streamed, connect_t, read_t, check, cert_file, key_file)
            self.cookies.extract(r._set_cookies, r._cookie_host, r._cookie_path)
            prev = new
        if history:
            r.history = history
        return r

    def _redirected(self, r: Response, prev: PreparedRequest) -> PreparedRequest:
        """The request a redirection r (a response to prev) asks for."""
        url = r.headers["location"]
        if url.startswith("//"):
            url = urlsplit(r.url).scheme + ":" + url
        parts = urlsplit(url)
        old_fragment = urlsplit(prev.url).fragment
        if parts.fragment == "" and old_fragment:
            url = url + "#" + old_fragment
        if not parts.netloc:
            url = urljoin(r.url, requote_uri(url))
        else:
            url = requote_uri(url)
        new = prev.copy()
        new.url = url
        method = new.method
        if r.status_code == 303 and method != "HEAD":
            method = "GET"
        if r.status_code == 302 and method != "HEAD":
            method = "GET"
        if r.status_code == 301 and method == "POST":
            method = "GET"
        new.method = method
        if r.status_code != 307 and r.status_code != 308:
            new.headers.pop("Content-Length")
            new.headers.pop("Content-Type")
            new.headers.pop("Transfer-Encoding")
            new.body = None
        new.headers.pop("Cookie")
        jar = prev._cookies.copy()
        jar.extract(r._set_cookies, r._cookie_host, r._cookie_path)
        jar.update(self.cookies)
        new.prepare_cookies(jar)
        if should_strip_auth(prev.url, url):
            new.headers.pop("Authorization")
        return new

    def get(self, url: str, params: _P = None, *, data: _D = None, headers: _H = None, cookies: _C = None, files: _F = None,
            auth: _A = None, timeout: _T = None, allow_redirects: bool = True, proxies: _X = None, hooks: _K = None,
            stream: bool | None = None, verify: _V = None, cert: _E = None, json: _J = None) -> Response:
        return self.request("GET", url, params, data, headers, cookies, files, auth, timeout, allow_redirects, proxies, hooks, stream, verify, cert, json)

    def options(self, url: str, *, params: _P = None, data: _D = None, headers: _H = None, cookies: _C = None, files: _F = None,
                auth: _A = None, timeout: _T = None, allow_redirects: bool = True, proxies: _X = None, hooks: _K = None,
                stream: bool | None = None, verify: _V = None, cert: _E = None, json: _J = None) -> Response:
        return self.request("OPTIONS", url, params, data, headers, cookies, files, auth, timeout, allow_redirects, proxies, hooks, stream, verify, cert, json)

    def head(self, url: str, *, params: _P = None, data: _D = None, headers: _H = None, cookies: _C = None, files: _F = None,
             auth: _A = None, timeout: _T = None, allow_redirects: bool = False, proxies: _X = None, hooks: _K = None,
             stream: bool | None = None, verify: _V = None, cert: _E = None, json: _J = None) -> Response:
        return self.request("HEAD", url, params, data, headers, cookies, files, auth, timeout, allow_redirects, proxies, hooks, stream, verify, cert, json)

    def post(self, url: str, data: _D = None, json: _J = None, *, params: _P = None, headers: _H = None, cookies: _C = None,
             files: _F = None, auth: _A = None, timeout: _T = None, allow_redirects: bool = True, proxies: _X = None,
             hooks: _K = None, stream: bool | None = None, verify: _V = None, cert: _E = None) -> Response:
        return self.request("POST", url, params, data, headers, cookies, files, auth, timeout, allow_redirects, proxies, hooks, stream, verify, cert, json)

    def put(self, url: str, data: _D = None, *, params: _P = None, headers: _H = None, cookies: _C = None, files: _F = None,
            auth: _A = None, timeout: _T = None, allow_redirects: bool = True, proxies: _X = None, hooks: _K = None,
            stream: bool | None = None, verify: _V = None, cert: _E = None, json: _J = None) -> Response:
        return self.request("PUT", url, params, data, headers, cookies, files, auth, timeout, allow_redirects, proxies, hooks, stream, verify, cert, json)

    def patch(self, url: str, data: _D = None, *, params: _P = None, headers: _H = None, cookies: _C = None, files: _F = None,
              auth: _A = None, timeout: _T = None, allow_redirects: bool = True, proxies: _X = None, hooks: _K = None,
              stream: bool | None = None, verify: _V = None, cert: _E = None, json: _J = None) -> Response:
        return self.request("PATCH", url, params, data, headers, cookies, files, auth, timeout, allow_redirects, proxies, hooks, stream, verify, cert, json)

    def delete(self, url: str, *, params: _P = None, data: _D = None, headers: _H = None, cookies: _C = None, files: _F = None,
               auth: _A = None, timeout: _T = None, allow_redirects: bool = True, proxies: _X = None, hooks: _K = None,
               stream: bool | None = None, verify: _V = None, cert: _E = None, json: _J = None) -> Response:
        return self.request("DELETE", url, params, data, headers, cookies, files, auth, timeout, allow_redirects, proxies, hooks, stream, verify, cert, json)


def session() -> Session:
    """A new Session."""
    return Session()
