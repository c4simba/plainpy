"""Authentication: HTTPBasicAuth (what auth=("user", "password") is), HTTPProxyAuth, and AuthBase,
the base of your own - a callable given the PreparedRequest, giving it back with its headers."""
import base64
from _ppy_typing import TypeVar
from .models import PreparedRequest

_A = TypeVar("_A")


def _basic_auth_str(username: str, password: str) -> str:
    """The Authorization header of Basic authentication."""
    return "Basic " + base64.b64encode((username + ":" + password).encode("latin-1")).decode("ascii")


class AuthBase:
    """The base of authentication classes: __call__(r) gives the PreparedRequest r back, authenticated."""

    def __call__(self, r: PreparedRequest) -> PreparedRequest:
        raise NotImplementedError("Auth hooks must be callable.")


class HTTPBasicAuth(AuthBase):
    """HTTP Basic Authentication of a user name and password."""

    def __init__(self, username: str, password: str) -> None:
        self.username = username
        self.password = password

    def __eq__(self, other) -> bool:
        if isinstance(other, HTTPBasicAuth):
            return self.username == other.username and self.password == other.password
        return False

    def __ne__(self, other) -> bool:
        return not self == other

    def __call__(self, r: PreparedRequest) -> PreparedRequest:
        r.headers["Authorization"] = _basic_auth_str(self.username, self.password)
        return r


class HTTPProxyAuth(HTTPBasicAuth):
    """HTTP Proxy Authentication (the Proxy-Authorization header)."""

    def __call__(self, r: PreparedRequest) -> PreparedRequest:
        r.headers["Proxy-Authorization"] = _basic_auth_str(self.username, self.password)
        return r


def apply_auth(r: PreparedRequest, auth: _A = None) -> PreparedRequest:
    """r authenticated by auth: (user, password) is Basic authentication, otherwise auth(r)."""
    if auth is None:
        return r
    elif isinstance(auth, tuple):
        return HTTPBasicAuth(auth[0], auth[1])(r)
    else:
        return auth(r)
