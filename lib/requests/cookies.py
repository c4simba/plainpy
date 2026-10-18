"""Cookies: a RequestsCookieJar holds a session's (and a response's), read from the Set-Cookie
headers of responses and sent in the Cookie header of the requests whose host, path and scheme
they are for."""
import time

_MONTHS: list[str] = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]


class Cookie:
    """One cookie: name and value, the domain and path it is for (domain "": every host), secure
    (https only), expires (seconds since 1970, None: until the session ends)."""

    def __init__(self, name: str, value: str, domain: str = "", path: str = "/", secure: bool = False,
                 expires: int | None = None, host_only: bool = False) -> None:
        self.name = name
        self.value = value
        self.domain = domain
        self.path = path
        self.secure = secure
        self.expires = expires
        self.host_only = host_only

    def is_expired(self, now: float) -> bool:
        exp = self.expires
        return exp is not None and exp <= now

    def matches(self, host: str, path: str, secure: bool) -> bool:
        """Is it sent to host for path (secure: over https)?"""
        if self.secure and not secure:
            return False
        d = self.domain
        if d:
            if self.host_only:
                if host != d:
                    return False
            elif host != d and not host.endswith("." + d):
                return False
        p = self.path or "/"
        if path != p and not path.startswith(p if p.endswith("/") else p + "/"):
            return False
        return True

    def __repr__(self) -> str:
        return "<Cookie " + self.name + "=" + self.value + " for " + self.domain + self.path + ">"


def _two(s: str) -> int:
    return int(s) if s.isdigit() else -1


def _expires(text: str) -> int | None:
    """The date of an Expires attribute (Wdy, DD Mon YYYY HH:MM:SS GMT and the older forms), else None."""
    day = -1
    month = -1
    year = -1
    hms: list[int] = []
    for tok in text.replace(",", " ").replace("-", " ").split():
        low = tok.lower()
        if ":" in tok and not hms:
            hms = [_two(p) for p in tok.split(":")]
        elif low[:3] in _MONTHS and month < 0:
            month = _MONTHS.index(low[:3]) + 1
        elif tok.isdigit():
            if len(tok) <= 2 and day < 0:
                day = int(tok)
            elif year < 0:
                year = int(tok)
    if year >= 0 and year < 70:
        year += 2000
    elif year >= 70 and year < 100:
        year += 1900
    if day < 1 or month < 1 or year < 1601 or len(hms) != 3 or min(hms) < 0:
        return None
    y = year - 1 if month <= 2 else year
    m = month + 9 if month <= 2 else month - 3
    era = y // 400
    yoe = y - era * 400
    doy = (153 * m + 2) // 5 + day - 1
    days = era * 146097 + yoe * 365 + yoe // 4 - yoe // 100 + doy - 719468
    return ((days * 24 + hms[0]) * 60 + hms[1]) * 60 + hms[2]


def parse_set_cookie(line: str, host: str, request_path: str) -> Cookie | None:
    """The cookie a Set-Cookie header of a response from host (for request_path) sets, None if it is
    not one or not for that host."""
    parts = line.split(";")
    name, eq, value = parts[0].partition("=")
    name = name.strip()
    if not eq or not name:
        return None
    domain = ""
    path = ""
    secure = False
    expires: int | None = None
    max_age = False
    for attr in parts[1:]:
        k, _, v = attr.partition("=")
        k = k.strip().lower()
        v = v.strip()
        if k == "domain" and v:
            domain = v.lstrip(".").lower()
        elif k == "path":
            path = v
        elif k == "secure":
            secure = True
        elif k == "max-age" and (v.isdigit() or (v[:1] == "-" and v[1:].isdigit())):
            expires = int(time.time()) + int(v)
            max_age = True
        elif k == "expires" and not max_age:
            expires = _expires(v)
    host = host.lower()
    host_only = domain == ""
    if host_only:
        domain = host
    elif host != domain and not host.endswith("." + domain):
        return None
    if not path.startswith("/"):
        path = request_path.rpartition("/")[0] or "/"
    return Cookie(name, value.strip(), domain, path, secure, expires, host_only)


class RequestsCookieJar:
    """Cookies by name (and domain and path): jar["name"], jar.get(name), jar.set(name, value),
    get_dict(); iterating gives the Cookie objects."""

    def __init__(self) -> None:
        self._cookies: list[Cookie] = []

    def set_cookie(self, cookie: Cookie) -> None:
        """cookie in the jar, in place of one of its name, domain and path."""
        self._cookies = [c for c in self._cookies
                         if not (c.name == cookie.name and c.domain == cookie.domain and c.path == cookie.path)]
        if not cookie.is_expired(time.time()):
            self._cookies.append(cookie)

    def set(self, name: str, value: str | None, domain: str = "", path: str = "/") -> Cookie | None:
        """A cookie set (value None: the ones of that name removed)."""
        if value is None:
            self._cookies = [c for c in self._cookies
                             if not (c.name == name and (not domain or c.domain == domain) and (path == "/" or c.path == path))]
            return None
        c = Cookie(name, value, domain, path)
        self.set_cookie(c)
        return c

    def _find(self, name: str, domain: str | None, path: str | None) -> Cookie | None:
        for c in self._cookies:
            if c.name == name and (domain is None or c.domain == domain) and (path is None or c.path == path):
                return c
        return None

    def get(self, name: str, default: str | None = None, domain: str | None = None, path: str | None = None) -> str | None:
        c = self._find(name, domain, path)
        if c is None:
            return default
        return c.value

    def __getitem__(self, name: str) -> str:
        c = self._find(name, None, None)
        if c is None:
            raise KeyError("name=" + repr(name) + ", domain=None, path=None")
        return c.value

    def __setitem__(self, name: str, value: str) -> None:
        self.set(name, value)

    def __delitem__(self, name: str) -> None:
        self.set(name, None)

    def __contains__(self, name: str) -> bool:
        return self._find(name, None, None) is not None

    def __len__(self) -> int:
        return len(self._cookies)

    def __iter__(self):
        for c in list(self._cookies):
            yield c

    def keys(self) -> list[str]:
        return [c.name for c in self._cookies]

    def values(self) -> list[str]:
        return [c.value for c in self._cookies]

    def items(self) -> list[tuple[str, str]]:
        return [(c.name, c.value) for c in self._cookies]

    def get_dict(self, domain: str | None = None, path: str | None = None) -> dict[str, str]:
        out: dict[str, str] = {}
        for c in self._cookies:
            if (domain is None or c.domain == domain) and (path is None or c.path == path):
                out[c.name] = c.value
        return out

    def list_domains(self) -> list[str]:
        out: list[str] = []
        for c in self._cookies:
            if c.domain not in out:
                out.append(c.domain)
        return out

    def list_paths(self) -> list[str]:
        out: list[str] = []
        for c in self._cookies:
            if c.path not in out:
                out.append(c.path)
        return out

    def update(self, other: "RequestsCookieJar") -> None:
        for c in other._cookies:
            self.set_cookie(c)

    def copy(self) -> "RequestsCookieJar":
        j = RequestsCookieJar()
        j._cookies = list(self._cookies)
        return j

    def clear(self, domain: str | None = None, path: str | None = None, name: str | None = None) -> None:
        self._cookies = [c for c in self._cookies
                         if not ((domain is None or c.domain == domain) and (path is None or c.path == path) and (name is None or c.name == name))]

    def extract(self, set_cookies: list[str], host: str, request_path: str) -> None:
        """The cookies of a response's Set-Cookie headers (one each) put in."""
        for line in set_cookies:
            c = parse_set_cookie(line, host, request_path)
            if c is not None:
                self._cookies = [o for o in self._cookies if not (o.name == c.name and o.domain == c.domain and o.path == c.path)]
                if not c.is_expired(time.time()):
                    self._cookies.append(c)

    def header(self, host: str, path: str, secure: bool) -> str:
        """The Cookie header to send to host for path ("" if no cookie is for it); expired ones dropped."""
        now = time.time()
        self._cookies = [c for c in self._cookies if not c.is_expired(now)]
        out = [c for c in self._cookies if c.matches(host.lower(), path, secure)]
        out.sort(key=lambda c: -len(c.path))
        return "; ".join(c.name + "=" + c.value for c in out)

    def __repr__(self) -> str:
        return "<RequestsCookieJar[" + ", ".join(repr(c) for c in self._cookies) + "]>"


def cookiejar_from_dict(cookie_dict: dict[str, str] | None, cookiejar: RequestsCookieJar | None = None) -> RequestsCookieJar:
    """A jar (cookiejar, else a new one) with the cookies of cookie_dict."""
    jar = cookiejar if cookiejar is not None else RequestsCookieJar()
    if cookie_dict is not None:
        for name in cookie_dict:
            jar.set(name, cookie_dict[name])
    return jar
