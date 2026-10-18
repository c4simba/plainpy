"""The connections of requests: http.client's, kept open between requests to the same scheme, host
and port (keep-alive), the TLS ones checked as verify says - the system's certificate authorities
("1"), none ("0"), or a file / folder of them."""
import sys
import os
from http.client import HTTPConnection, HTTPSConnection

if sys.platform in ("linux", "darwin", "kolibrios"):
    import ssl

    _contexts: dict[str, ssl.SSLContext] = {}

    def _context(verify: str, cert_file: str, key_file: str) -> ssl.SSLContext:
        key = verify + "\n" + cert_file + "\n" + key_file
        if key in _contexts:
            return _contexts[key]
        if verify == "0":
            ctx = ssl._create_unverified_context()
        elif verify == "1":
            ctx = ssl.create_default_context()
        elif os.path.isdir(verify):
            ctx = ssl.create_default_context(capath=verify)
        else:
            ctx = ssl.create_default_context(cafile=verify)
        if cert_file:
            ctx.load_cert_chain(cert_file, key_file if key_file else None)
        _contexts[key] = ctx
        return ctx

    def open_connection(scheme: str, host: str, port: int, timeout: float | None, verify: str,
                        cert_file: str, key_file: str) -> HTTPConnection:
        """A connection (not connected yet) to host:port."""
        if scheme == "https":
            return HTTPSConnection(host, port, timeout, None, _context(verify, cert_file, key_file))
        return HTTPConnection(host, port, timeout)

    def is_tls_error(e: OSError) -> bool:
        return isinstance(e, ssl.SSLError)
else:
    def open_connection(scheme: str, host: str, port: int, timeout: float | None, verify: str,
                        cert_file: str, key_file: str) -> HTTPConnection:
        """A connection (not connected yet) to host:port (https: no TLS here - connecting raises)."""
        if scheme == "https":
            return HTTPSConnection(host, port, timeout)
        return HTTPConnection(host, port, timeout)

    def is_tls_error(e: OSError) -> bool:
        return False


class Pool:
    """The idle connections, by scheme://host:port and how TLS is checked."""

    def __init__(self) -> None:
        self._idle: dict[str, list[HTTPConnection]] = {}
        self.closed = False

    def take(self, key: str) -> HTTPConnection | None:
        """An idle connection for key (taken out), else None."""
        if key in self._idle:
            conns = self._idle[key]
            while conns:
                conn = conns.pop()
                if conn.sock is not None:
                    return conn
        return None

    def give(self, key: str, conn: HTTPConnection) -> None:
        """conn idle again (its response read to the end): kept for key, closed if the pool is."""
        if self.closed or conn.sock is None:
            conn.close()
            return
        if key not in self._idle:
            self._idle[key] = []
        self._idle[key].append(conn)

    def close(self) -> None:
        self.closed = True
        for key in self._idle:
            for conn in self._idle[key]:
                conn.close()
        self._idle = {}
