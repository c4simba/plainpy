"""requests' helpers: the default headers, the charset of a response, URLs (requoted, the user name
and password in them), Link headers."""
from urllib.parse import quote, unquote, urlsplit
from .structures import CaseInsensitiveDict

VERSION = "2.32.5"                      # (the requests whose API this is)
DEFAULT_ACCEPT_ENCODING = "gzip, deflate"
DEFAULT_PORTS: dict[str, int] = {"http": 80, "https": 443}
REDIRECT_STATI = (301, 302, 303, 307, 308)
_UNRESERVED = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"


def default_user_agent(name: str = "python-requests") -> str:
    """The User-Agent sent: python-requests/2.32.5."""
    return name + "/" + VERSION


def default_headers() -> CaseInsensitiveDict:
    """The headers of every request (a session's to begin with)."""
    return CaseInsensitiveDict({"User-Agent": default_user_agent(), "Accept-Encoding": DEFAULT_ACCEPT_ENCODING,
                                "Accept": "*/*", "Connection": "keep-alive"})


def _parse_content_type_header(header: str) -> tuple[str, dict[str, str]]:
    """Content-Type's type and its parameters (names in lower case, quotes taken off)."""
    tokens = header.split(";")
    params: dict[str, str] = {}
    for param in tokens[1:]:
        param = param.strip()
        if param:
            key = param
            value = ""
            i = param.find("=")
            if i >= 0:
                key = param[:i].strip("\"' ")
                value = param[i + 1:].strip("\"' ")
            params[key.lower()] = value
    return (tokens[0].strip(), params)


def get_encoding_from_headers(headers: CaseInsensitiveDict) -> str | None:
    """The charset of Content-Type; text/*: ISO-8859-1, application/json: utf-8 when it has none."""
    content_type = headers.get("content-type")
    if not content_type:
        return None
    ctype, params = _parse_content_type_header(content_type)
    if "charset" in params:
        return params["charset"].strip("'\"")
    if "text" in ctype:
        return "ISO-8859-1"
    if "application/json" in ctype:
        return "utf-8"
    return None


def unquote_unreserved(uri: str) -> str:
    """%XX escapes of unreserved characters (letters, digits, -._~) made the characters; the others kept."""
    parts = uri.split("%")
    for i in range(1, len(parts)):
        h = parts[i][0:2]
        if len(h) == 2 and h.isalnum():
            try:
                c = chr(int(h, 16))
            except ValueError:
                from .exceptions import InvalidURL
                raise InvalidURL("Invalid percent-escape sequence: '" + h + "'")
            if c in _UNRESERVED:
                parts[i] = c + parts[i][2:]
            else:
                parts[i] = "%" + parts[i]
        else:
            parts[i] = "%" + parts[i]
    return "".join(parts)


def requote_uri(uri: str) -> str:
    """uri with what is not allowed in a URL quoted, the escapes already there kept."""
    from .exceptions import InvalidURL
    try:
        return quote(unquote_unreserved(uri), safe="!#$%&'()*+,/:;=?@[]~")
    except InvalidURL:
        return quote(uri, safe="!#$&'()*+,/:;=?@[]~")


def get_auth_from_url(url: str) -> tuple[str, str]:
    """The user name and password of url (http://user:pass@host/), else ("", "")."""
    parts = urlsplit(url)
    user = parts.username
    password = parts.password
    if user is None or password is None:
        return ("", "")
    return (unquote(user), unquote(password))


def parse_header_links(value: str) -> list[dict[str, str]]:
    """A Link header as dicts: "url" and the parameters (rel, type ...)."""
    links: list[dict[str, str]] = []
    value = value.strip(" '\"")
    if not value:
        return links
    vals: list[str] = []
    for piece in value.split(","):
        if vals and not piece.lstrip(" ").startswith("<"):
            vals[-1] += "," + piece
        else:
            vals.append(piece)
    for val in vals:
        url, sep, params = val.partition(";")
        link: dict[str, str] = {"url": url.strip("<> '\"")}
        for param in params.split(";"):
            kv = param.split("=")
            if len(kv) != 2:
                break
            link[kv[0].strip(" '\"")] = kv[1].strip(" '\"")
        links.append(link)
    return links


def iter_slices(data: bytes, slice_length: int):
    """data in pieces of slice_length bytes."""
    pos = 0
    if slice_length <= 0:
        slice_length = len(data)
    while pos < len(data):
        yield data[pos:pos + slice_length]
        pos += slice_length
