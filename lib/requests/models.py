"""The objects of requests: PreparedRequest (what is sent: method, URL, headers, body), Response
(what came back: the status, the headers, the body as bytes, text or JSON) and Request (a request
to prepare). PreparedRequest.body is bytes (requests: a str for form data and str bodies)."""
import sys
import json as _json
import random
import zlib
from datetime import timedelta
from urllib.parse import urlsplit, quote_plus
from http.client import HTTPResponse, HTTPConnection, HTTPException, IncompleteRead
from _ppy_typing import TypeVar
from .structures import CaseInsensitiveDict
from .cookies import RequestsCookieJar
from .connections import Pool
from .utils import get_encoding_from_headers, requote_uri, parse_header_links, iter_slices, REDIRECT_STATI

_P = TypeVar("_P")                      # params: a dict (values: str, int ..., a list of them), a list of pairs, a str
_D = TypeVar("_D")                      # data: a dict / list of pairs (a form), a str, bytes, a file
_F = TypeVar("_F")                      # files: a dict / list of pairs of bytes, str, files, (name, content[, type])
_J = TypeVar("_J")                      # json: what json.dumps writes
_H = TypeVar("_H")                      # headers: a dict[str, str] or a CaseInsensitiveDict
_V = TypeVar("_V")
_X = TypeVar("_X")
_C = TypeVar("_C")                      # cookies: a dict[str, str] or a RequestsCookieJar
_K = TypeVar("_K")

CONTENT_CHUNK_SIZE = 10 * 1024
ITER_CHUNK_SIZE = 512


def _text_of(v: _V) -> str:
    if isinstance(v, str):
        return v
    elif isinstance(v, bytes):
        return v.decode("utf-8")
    else:
        return str(v)


def _pairs(data: _D = None) -> list[tuple[str, str]]:
    """The fields of params or of a form: a dict (a list as a value: a field for each item) or a list of pairs."""
    out: list[tuple[str, str]] = []
    if data is None:
        return out
    elif isinstance(data, dict):
        for k in data:
            v = data[k]
            if isinstance(v, list):
                for x in v:
                    if x is not None:
                        out.append((_text_of(k), _text_of(x)))
            elif v is not None:
                out.append((_text_of(k), _text_of(v)))
    elif isinstance(data, list):
        for k, v in data:
            if v is not None:
                out.append((_text_of(k), _text_of(v)))
    return out


def _encode_params(data: _P = None) -> str:
    """params (or form data) as a query string: a str as it is, the others urlencoded."""
    if data is None:
        return ""
    elif isinstance(data, str):
        return data
    elif isinstance(data, bytes):
        return data.decode("ascii")
    else:
        return "&".join(quote_plus(k) + "=" + quote_plus(v) for k, v in _pairs(data))


def _header_param(name: str, value: str) -> str:
    """name="value" of a multipart header (quotes, backslashes and line ends escaped as browsers do)."""
    v = value.replace("\\", "\\\\").replace('"', "%22").replace("\r", "%0D").replace("\n", "%0A")
    return name + '="' + v + '"'


def _file_content(fp: _X = None) -> bytes:
    if fp is None:
        return b""
    elif isinstance(fp, bytes):
        return fp
    elif isinstance(fp, str):
        return fp.encode("utf-8")
    elif isinstance(fp, bytearray):
        return bytes(fp)
    elif hasattr(fp, "read"):
        return _file_content(fp.read())
    else:
        return str(fp).encode("utf-8")


def _file_name(fp: _X, default: str) -> str:
    """A file's name (its base name), else default."""
    if hasattr(fp, "name"):
        name = fp.name
        if isinstance(name, str):
            if name and name[0] != "<" and name[-1] != ">":
                return name.replace("\\", "/").rpartition("/")[2]
    return default


def _file_part(name: str, v: _X) -> bytes:
    """A file of files (the content, (filename, content), (filename, content, type)) as a part of the body."""
    ftype = ""
    if isinstance(v, tuple):
        fname = v[0]
        data = _file_content(v[1])
        if len(v) >= 3:
            ftype = v[2]
    else:
        fname = _file_name(v, name)
        data = _file_content(v)
    head = "Content-Disposition: form-data; " + _header_param("name", name)
    if fname is not None:
        head += "; " + _header_param("filename", fname)
    if ftype:
        head += "\r\nContent-Type: " + ftype
    return (head + "\r\n\r\n").encode("utf-8") + data


def _encode_files(files: _F = None, data: _D = None) -> tuple[bytes, str]:
    """A multipart/form-data body of the fields of data and the files: (body, its Content-Type)."""
    if files is None:
        return (b"", "")
    if isinstance(data, str):
        raise ValueError("Data must not be a string.")
    boundary = "".join(random.choice("0123456789abcdef") for _ in range(32))
    sep = ("--" + boundary + "\r\n").encode("latin-1")
    parts: list[bytes] = []
    for k, v in _pairs(data):
        parts.append(sep + ("Content-Disposition: form-data; " + _header_param("name", k) + "\r\n\r\n" + v).encode("utf-8") + b"\r\n")
    if isinstance(files, dict):
        for k in files:
            parts.append(sep + _file_part(_text_of(k), files[k]) + b"\r\n")
    elif isinstance(files, list):
        for k, v in files:
            parts.append(sep + _file_part(_text_of(k), v) + b"\r\n")
    parts.append(("--" + boundary + "--\r\n").encode("latin-1"))
    return (b"".join(parts), "multipart/form-data; boundary=" + boundary)


def _empty(v: _V = None) -> bool:
    """Is v None or empty (no data, no files)?"""
    if v is None:
        return True
    else:
        return not v


def _data_body(data: _D = None) -> tuple[bytes | None, str]:
    """The body data makes and its Content-Type ("": none)."""
    if data is None:
        return (None, "")
    elif isinstance(data, str):
        return (data.encode("latin-1"), "")
    elif isinstance(data, bytes):
        return (data, "")
    elif isinstance(data, dict):
        return (_encode_params(data).encode("latin-1"), "application/x-www-form-urlencoded")
    elif isinstance(data, list):
        return (_encode_params(data).encode("latin-1"), "application/x-www-form-urlencoded")
    elif hasattr(data, "read"):
        return (_file_content(data), "")
    else:
        return (None, "")


def _check_header(name: str, value: _V) -> None:
    from .exceptions import InvalidHeader
    if not isinstance(value, str):
        raise InvalidHeader("Header part (" + repr(value) + ") from (" + repr(name) + ", " + repr(value) + ") must be of type str or bytes, not " + str(type(value)))
    if not name or name[0] in " \t" or any(c in name for c in ":\r\n"):
        raise InvalidHeader("Invalid leading whitespace, reserved character(s), or return character(s) in header name: " + repr(name))
    if value and (value[0] in " \t" or "\r" in value or "\n" in value):
        raise InvalidHeader("Invalid leading whitespace, reserved character(s), or return character(s) in header value: " + repr(value))


class PreparedRequest:
    """What is sent: method, url, headers, body (bytes, None: no body)."""

    def __init__(self) -> None:
        self.method = ""
        self.url = ""
        self.headers = CaseInsensitiveDict()
        self.body: bytes | None = None
        self._cookies = RequestsCookieJar()

    def prepare_method(self, method: str) -> None:
        self.method = method.upper()

    def prepare_url(self, url: str, params: _P = None) -> None:
        """url (params added to its query) requoted; MissingSchema, InvalidURL when it is not one."""
        from .exceptions import MissingSchema, InvalidURL
        url = url.lstrip()
        if ":" in url and not url.lower().startswith("http"):
            self.url = url                                  # (mailto:, data: ... as they are)
            return
        try:
            parts = urlsplit(url)
            port = parts.port
        except ValueError as e:
            raise InvalidURL(str(e))
        if not parts.scheme:
            raise MissingSchema("Invalid URL " + repr(url) + ": No scheme supplied. Perhaps you meant https://" + url + "?")
        host = parts.hostname
        if not host:
            raise InvalidURL("Invalid URL " + repr(url) + ": No host supplied")
        if not host.isascii() or host.startswith("*") or host.startswith("."):
            raise InvalidURL("URL has an invalid label.")
        if ":" in host:
            host = "[" + host + "]"
        netloc = parts.netloc.rpartition("@")
        auth = netloc[0] if netloc[1] else ""
        loc = auth + "@" + host if auth else host
        if port is not None:
            loc += ":" + str(port)
        query = parts.query
        enc = _encode_params(params)
        if enc:
            query = query + "&" + enc if query else enc
        full = parts.scheme + "://" + loc + (parts.path or "/")
        if query:
            full += "?" + query
        if parts.fragment:
            full += "#" + parts.fragment
        self.url = requote_uri(full)

    def prepare_headers(self, headers: _H = None) -> None:
        self.headers = CaseInsensitiveDict()
        if headers is None:
            return
        elif isinstance(headers, CaseInsensitiveDict):
            for k, v in headers.items():
                _check_header(k, v)
                self.headers[k] = v
        elif isinstance(headers, dict):
            for k in headers:
                v = headers[k]
                if v is not None:
                    _check_header(k, v)
                    self.headers[k] = v

    def prepare_body(self, data: _D = None, files: _F = None, json: _J = None) -> None:
        """The body of data (a form, a str, bytes, a file), files (multipart) or json; its
        Content-Type and Content-Length."""
        body: bytes | None = None
        content_type = ""
        if json is not None:
            if _empty(data):
                content_type = "application/json"
                body = _json.dumps(json).encode("utf-8")
        if not _empty(files):
            body, content_type = _encode_files(files, data)
        elif not _empty(data):
            body, content_type = _data_body(data)
        self.prepare_content_length(body)
        if content_type and "content-type" not in self.headers:
            self.headers["Content-Type"] = content_type
        self.body = body

    def prepare_content_length(self, body: bytes | None) -> None:
        if body is not None:
            if len(body):
                self.headers["Content-Length"] = str(len(body))
        elif self.method not in ("GET", "HEAD") and self.headers.get("Content-Length") is None:
            self.headers["Content-Length"] = "0"

    def prepare_cookies(self, cookies: RequestsCookieJar) -> None:
        """The Cookie header of the cookies of the jar that are for this URL (unless there is one)."""
        self._cookies = cookies
        if "cookie" in self.headers:
            return
        parts = urlsplit(self.url)
        header = cookies.header(parts.hostname or "", parts.path or "/", parts.scheme == "https")
        if header:
            self.headers["Cookie"] = header

    @property
    def path_url(self) -> str:
        """The path and query of the URL (what the request line has)."""
        parts = urlsplit(self.url)
        path = parts.path or "/"
        if parts.query:
            path += "?" + parts.query
        return path

    def copy(self) -> "PreparedRequest":
        p = PreparedRequest()
        p.method = self.method
        p.url = self.url
        p.headers = self.headers.copy()
        p.body = self.body
        p._cookies = self._cookies.copy()
        return p

    def __repr__(self) -> str:
        return "<PreparedRequest [" + self.method + "]>"


class _Decoder:
    """Content-Encoding gzip / deflate undone as the body comes."""

    def __init__(self, encoding: str) -> None:
        self.encoding = encoding
        self._d = zlib.decompressobj(47)               # (a zlib or gzip header)
        self._first = True

    def decompress(self, data: bytes) -> bytes:
        try:
            out = self._d.decompress(data)
        except zlib.error:
            if not (self._first and self.encoding == "deflate"):
                raise
            self._d = zlib.decompressobj(-15)          # (deflate without its zlib header)
            out = self._d.decompress(data)
        self._first = False
        return out

    def flush(self) -> bytes:
        return self._d.flush()


class Response:
    """A response: status_code, reason, headers, url, content (bytes), text, json(), cookies,
    history (the redirections that led here), elapsed, request."""

    def __init__(self) -> None:
        self._content: bytes | None = None
        self._content_consumed = False
        self.status_code = 0
        self.headers = CaseInsensitiveDict()
        self.raw: HTTPResponse | None = None
        self.url = ""
        self.encoding: str | None = None
        self.history: list[Response] = []
        self.reason = ""
        self.cookies = RequestsCookieJar()
        self.elapsed = timedelta(0)
        self.request: PreparedRequest | None = None
        self._decoder: _Decoder | None = None
        self._pool: Pool | None = None
        self._pool_key = ""
        self._conn: HTTPConnection | None = None
        self._set_cookies: list[str] = []          # (its Set-Cookie headers, for the session's jar: deletions too)
        self._cookie_host = ""
        self._cookie_path = "/"

    def __repr__(self) -> str:
        return "<Response [" + str(self.status_code) + "]>"

    def __bool__(self) -> bool:
        return self.ok

    def __iter__(self):
        return self.iter_content(128)

    def __enter__(self) -> "Response":
        return self

    def __exit__(self, et, ev, tb) -> bool:
        self.close()
        return False

    @property
    def ok(self) -> bool:
        """No error status (below 400)."""
        return self.status_code < 400

    @property
    def is_redirect(self) -> bool:
        return "location" in self.headers and self.status_code in REDIRECT_STATI

    @property
    def is_permanent_redirect(self) -> bool:
        return "location" in self.headers and self.status_code in (301, 308)

    def _release(self) -> None:
        """The body read to its end: the connection kept for the next request."""
        conn = self._conn
        pool = self._pool
        self._conn = None
        if conn is not None and pool is not None:
            pool.give(self._pool_key, conn)

    def _drop(self) -> None:
        conn = self._conn
        self._conn = None
        if conn is not None:
            conn.close()

    def _raw_read(self, n: int) -> bytes:
        """Up to n bytes more of the body (all: n < 0), Content-Encoding undone; b"" at its end."""
        from .exceptions import ChunkedEncodingError, ConnectionError, ContentDecodingError
        raw = self.raw
        while raw is not None:
            try:
                data = raw.read(None if n < 0 else n)
            except IncompleteRead as e:
                self._drop()
                raise ChunkedEncodingError("Connection broken: " + repr(e), request=self.request)
            except HTTPException as e:
                self._drop()
                raise ChunkedEncodingError("Connection broken: " + repr(e), request=self.request)
            except TimeoutError:
                self._drop()
                raise ConnectionError("Read timed out.", request=self.request)
            except OSError as e:
                self._drop()
                raise ConnectionError("Connection broken: " + str(e), request=self.request)
            dec = self._decoder
            if not data or n < 0:
                out = data
                if dec is not None:
                    try:
                        out = dec.decompress(data) + dec.flush() if data else dec.flush()
                    except zlib.error as e:
                        self._drop()
                        raise ContentDecodingError("Received response with content-encoding: " + dec.encoding + ", but failed to decode it.", request=self.request)
                self.raw = None
                if raw.isclosed():
                    self._release()
                else:
                    self._drop()
                return out
            if dec is None:
                return data
            try:
                out = dec.decompress(data)
            except zlib.error as e:
                self._drop()
                raise ContentDecodingError("Received response with content-encoding: " + dec.encoding + ", but failed to decode it.", request=self.request)
            if out:
                return out
        return b""

    def iter_content(self, chunk_size: int = 1, decode_unicode: bool = False):
        """The body in pieces of chunk_size bytes (stream=True: as it comes)."""
        from .exceptions import StreamConsumedError
        if self._content is not None:
            for piece in iter_slices(self._content, chunk_size):
                yield piece
            return
        if self._content_consumed:
            raise StreamConsumedError()
        self._content_consumed = True
        size = chunk_size if chunk_size > 0 else CONTENT_CHUNK_SIZE
        while True:
            piece = self._raw_read(size)
            if not piece:
                break
            yield piece

    def iter_lines(self, chunk_size: int = ITER_CHUNK_SIZE, decode_unicode: bool = False, delimiter: bytes | None = None):
        """The body line by line (without the line ends; delimiter: split there instead)."""
        pending: bytes | None = None
        for chunk in self.iter_content(chunk_size):
            if pending is not None:
                chunk = pending + chunk
            if delimiter is not None:
                lines = chunk.split(delimiter)
            else:
                lines = chunk.splitlines()
            if lines and lines[-1] and chunk and lines[-1][-1:] == chunk[-1:]:
                pending = lines.pop()
            else:
                pending = None
            for line in lines:
                yield line
        if pending is not None:
            yield pending

    if not sys._compiled:
        _iter_content_bytes = iter_content
        _iter_lines_bytes = iter_lines

        def iter_content(self, chunk_size=1, decode_unicode=False):
            if not decode_unicode:
                return self._iter_content_bytes(chunk_size)
            return self._decode_stream(self._iter_content_bytes(chunk_size))

        def iter_lines(self, chunk_size=ITER_CHUNK_SIZE, decode_unicode=False, delimiter=None):
            if not decode_unicode:
                return self._iter_lines_bytes(chunk_size, False, delimiter)
            return self._decode_lines(chunk_size, delimiter)

        def _decode_stream(self, chunks):
            import codecs
            if self.encoding is None:
                yield from chunks
                return
            decoder = codecs.getincrementaldecoder(self.encoding)(errors="replace")
            for chunk in chunks:
                rv = decoder.decode(chunk)
                if rv:
                    yield rv
            rv = decoder.decode(b"", final=True)
            if rv:
                yield rv

        def _decode_lines(self, chunk_size, delimiter):
            pending = None
            for chunk in self.iter_content(chunk_size, True):
                if pending is not None:
                    chunk = pending + chunk
                lines = chunk.split(delimiter) if delimiter else chunk.splitlines()
                if lines and lines[-1] and chunk and lines[-1][-1] == chunk[-1]:
                    pending = lines.pop()
                else:
                    pending = None
                yield from lines
            if pending is not None:
                yield pending

    @property
    def content(self) -> bytes:
        """The body (bytes), Content-Encoding (gzip, deflate) undone."""
        c = self._content
        if c is None:
            if self._content_consumed:
                raise RuntimeError("The content for this response was already consumed")
            c = self._raw_read(-1)
            self._content = c
            self._content_consumed = True
        return c

    @property
    def apparent_encoding(self) -> str:
        """A guess of the body's charset: ascii, utf-8, else ISO-8859-1."""
        c = self.content
        if c.isascii():
            return "ascii"
        try:
            c.decode("utf-8")
            return "utf-8"
        except UnicodeDecodeError:
            return "ISO-8859-1"

    @property
    def text(self) -> str:
        """The body decoded: by encoding (the charset of Content-Type), else apparent_encoding."""
        c = self.content
        if not c:
            return ""
        enc = self.encoding
        if enc is None:
            enc = self.apparent_encoding
        try:
            return c.decode(enc, "replace")
        except LookupError:
            return c.decode("utf-8", "replace")

    def _json_text(self) -> str:
        """The body as JSON text: decoded by encoding, else as UTF-8 (UTF-16 / UTF-32: by their BOM or zeros)."""
        c = self.content
        if self.encoding is None and len(c) > 3:
            if c[:3] == b"\xef\xbb\xbf":
                return c[3:].decode("utf-8", "replace")
            if c[:2] in (b"\xff\xfe", b"\xfe\xff") or c[0] == 0 or c[1] == 0:
                enc = "utf-16"
                if c[:4] in (b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff") or (c[0] == 0 and c[1] == 0) or (c[2] == 0 and c[3] == 0):
                    enc = "utf-32"
                try:
                    return c.decode(enc)
                except UnicodeDecodeError:
                    pass
            return c.decode("utf-8", "replace")
        return self.text

    def _to_json(self) -> str:
        """(compiled programs: r.json() is json.loads(r._to_json()), of the type its result goes to)"""
        return self._json_text()

    if not sys._compiled:
        def json(self, **kwargs):
            """The body as JSON (the value of json.loads); JSONDecodeError if it is not."""
            from .exceptions import JSONDecodeError
            try:
                return _json.loads(self._json_text(), **kwargs)
            except _json.JSONDecodeError as e:
                raise JSONDecodeError(e.msg, e.doc, e.pos)

    @property
    def links(self) -> dict[str, dict[str, str]]:
        """The Link header's links by rel (else url)."""
        out: dict[str, dict[str, str]] = {}
        header = self.headers.get("link")
        if header:
            for link in parse_header_links(header):
                key = link["rel"] if "rel" in link else link["url"]
                out[key] = link
        return out

    @property
    def next(self) -> PreparedRequest | None:
        return None

    def raise_for_status(self) -> None:
        """HTTPError for a 4xx / 5xx status."""
        from .exceptions import HTTPError
        msg = ""
        if 400 <= self.status_code < 500:
            msg = str(self.status_code) + " Client Error: " + self.reason + " for url: " + self.url
        elif 500 <= self.status_code < 600:
            msg = str(self.status_code) + " Server Error: " + self.reason + " for url: " + self.url
        if msg:
            raise HTTPError(msg, response=self)

    def close(self) -> None:
        """The connection given back (the body read to its end) or closed."""
        raw = self.raw
        if raw is not None:
            self.raw = None
            raw.close()
            self._drop()
        self._release()


class Request:
    """A request to prepare (prepare(), Session.prepare_request()): method, url and what goes with it."""

    def __init__(self, method: str = "GET", url: str = "", headers: _H = None, files: _F = None, data: _D = None,
                 params: _P = None, auth: _X = None, cookies: _C = None, hooks: _K = None, json: _J = None) -> None:
        self.method = method
        self.url = url
        p = PreparedRequest()
        p.prepare_method(method)
        p.prepare_url(url, params)
        p.prepare_headers(headers)
        if cookies is not None:
            from .cookies import cookiejar_from_dict
            if isinstance(cookies, RequestsCookieJar):
                p.prepare_cookies(cookies)
            else:
                p.prepare_cookies(cookiejar_from_dict(cookies))
        p.prepare_body(data, files, json)
        self.has_auth = False
        if auth is not None:
            from .auth import apply_auth
            p = apply_auth(p, auth)
            self.has_auth = True
        self._prepared = p

    def prepare(self) -> PreparedRequest:
        """What is sent (a copy of it)."""
        return self._prepared.copy()

    def __repr__(self) -> str:
        return "<Request [" + self.method + "]>"
