"""The transport of requests: HTTPAdapter sends a PreparedRequest over http.client (a connection to
the same scheme, host and port used again once a response is read) and makes the Response; the
errors of sockets, TLS and HTTP become requests' exceptions."""
import time
from datetime import timedelta
from urllib.parse import urlsplit
from http.client import HTTPConnection, HTTPException, RemoteDisconnected
from .models import PreparedRequest, Response, _Decoder
from .connections import Pool, open_connection, is_tls_error
from .utils import get_encoding_from_headers, DEFAULT_PORTS
from .exceptions import ConnectTimeout, ReadTimeout, SSLError, InvalidSchema, InvalidURL
from .exceptions import ConnectionError as RequestsConnectionError


class BaseAdapter:
    """The base of transports (Session.mount(prefix, adapter))."""

    def close(self) -> None:
        pass


class HTTPAdapter(BaseAdapter):
    """http:// and https:// over http.client, the connections kept open (pool_connections,
    pool_maxsize, max_retries, pool_block: requests' names, not used here)."""

    def __init__(self, pool_connections: int = 10, pool_maxsize: int = 10, max_retries: int = 0, pool_block: bool = False) -> None:
        self.max_retries = max_retries
        self._pool = Pool()

    def close(self) -> None:
        """The idle connections closed."""
        self._pool.close()
        self._pool = Pool()

    def _connect(self, scheme: str, host: str, port: int, connect_timeout: float | None, read_timeout: float | None,
                 verify: str, cert_file: str, key_file: str, where: str, request: PreparedRequest) -> HTTPConnection:
        timeout = connect_timeout if connect_timeout is not None else read_timeout
        conn = open_connection(scheme, host, port, timeout, verify, cert_file, key_file)
        try:
            conn.connect()
        except TimeoutError:
            conn.close()
            raise ConnectTimeout(where + ": Max retries exceeded with url: " + request.path_url + " (Caused by ConnectTimeoutError('Connection to "
                                 + host + " timed out. (connect timeout=" + str(timeout) + ")'))", request=request)
        except OSError as e:
            conn.close()
            if is_tls_error(e):
                raise SSLError(where + ": Max retries exceeded with url: " + request.path_url + " (Caused by SSLError(" + repr(e) + "))", request=request)
            raise RequestsConnectionError(where + ": Max retries exceeded with url: " + request.path_url
                                          + " (Caused by NewConnectionError('Failed to establish a new connection: " + str(e) + "'))", request=request)
        except HTTPException as e:
            conn.close()
            raise RequestsConnectionError(where + ": " + str(e), request=request)
        sock = conn.sock
        if sock is not None and connect_timeout is not None and read_timeout is not None and read_timeout != connect_timeout:
            sock.settimeout(read_timeout)
        return conn

    def send(self, request: PreparedRequest, stream: bool = False, connect_timeout: float | None = None,
             read_timeout: float | None = None, verify: str = "1", cert_file: str = "", key_file: str = "") -> Response:
        """The response to request (stream: its body read later, by content / iter_content)."""
        parts = urlsplit(request.url)
        scheme = parts.scheme.lower()
        if scheme != "http" and scheme != "https":
            raise InvalidSchema("No connection adapters were found for " + repr(request.url))
        host = parts.hostname or ""
        try:
            given = parts.port
        except ValueError as e:
            raise InvalidURL(str(e), request=request)
        port = DEFAULT_PORTS[scheme] if given is None else given
        key = scheme + "://" + host + ":" + str(port) + "\n" + verify + "\n" + cert_file + "\n" + key_file
        where = ("HTTPSConnectionPool" if scheme == "https" else "HTTPConnectionPool") + "(host=" + repr(host) + ", port=" + str(port) + ")"
        headers: dict[str, str] = {}
        for k, v in request.headers.items():
            headers[k] = v
        started = time.monotonic()
        while True:
            conn = self._pool.take(key)
            reused = conn is not None
            if conn is None:
                conn = self._connect(scheme, host, port, connect_timeout, read_timeout, verify, cert_file, key_file, where, request)
            elif read_timeout is not None:
                sock = conn.sock
                if sock is not None and sock.gettimeout() is not None:
                    sock.settimeout(read_timeout)
            try:
                conn.request(request.method, request.path_url, request.body, headers)
                resp = conn.getresponse()
                break
            except (BrokenPipeError, ConnectionResetError, RemoteDisconnected) as e:
                conn.close()
                if reused:
                    continue                                # (the server closed the idle connection: a new one)
                raise RequestsConnectionError("('Connection aborted.', " + repr(e) + ")", request=request)
            except TimeoutError:
                conn.close()
                raise ReadTimeout(where + ": Read timed out. (read timeout=" + str(read_timeout) + ")", request=request)
            except OSError as e:
                conn.close()
                if is_tls_error(e):
                    raise SSLError(where + ": Max retries exceeded with url: " + request.path_url + " (Caused by SSLError(" + repr(e) + "))", request=request)
                raise RequestsConnectionError("('Connection aborted.', " + repr(e) + ")", request=request)
            except HTTPException as e:
                conn.close()
                raise RequestsConnectionError("('Connection aborted.', " + repr(e) + ")", request=request)
        r = Response()
        r.status_code = resp.status
        r.reason = resp.reason
        for k, v in resp.getheaders():
            r.headers._add(k, v)
        r.encoding = get_encoding_from_headers(r.headers)
        r.raw = resp
        r.url = request.url
        r.request = request
        set_cookies = resp.headers.get_all("set-cookie")
        if set_cookies is not None:
            r.cookies.extract(set_cookies, host, parts.path or "/")
            r._set_cookies = set_cookies
            r._cookie_host = host
            r._cookie_path = parts.path or "/"
        r.elapsed = timedelta(seconds=time.monotonic() - started)
        coding = (r.headers.get("content-encoding") or "").strip().lower()
        if request.method != "HEAD" and (coding == "gzip" or coding == "x-gzip" or coding == "deflate"):
            r._decoder = _Decoder(coding)
        r._pool = self._pool
        r._pool_key = key
        if conn.sock is not None:
            r._conn = conn                                  # (given back when the body is read)
        if not stream:
            r.content
        return r
