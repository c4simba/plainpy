"""The HTTP server of tests/run_requests_tests.sh, run by CPython: one port over plain HTTP, one over
TLS (tests/ssl/cert.pem: localhost, 127.0.0.1), HTTP/1.1 with keep-alive. Prints the two ports,
then serves until killed. The answers (JSON objects of strings, mostly) say what the request was:

  /get /anything...   {method, path, args, content-type, content-length, x-test, authorization,
                       cookie, body, conn}  (conn: the number of the connection: reuse shows)
  /status/N           status N
  /redirect/N         302 to /redirect/N-1 ... /get        /redirect-to?url=U&status=S
  /cookies/set?k=v    Set-Cookie k=v, 302 to /cookies       /cookies: the Cookie header
  /basic-auth/U/P     401 unless Basic U:P                  /gzip /deflate: compressed JSON
  /stream/N           N lines, chunked                      /bytes/N: N bytes (i % 256)
  /delay/S            after S seconds                       /latin1: text/html; charset=iso-8859-1
  /numbers            {"a": [1, 2], "b": [3]}               /bad-json: not JSON
  /links              a Link header                         /multi: Set-Cookie and X-Multi twice"""
import base64
import gzip
import json
import os
import socket
import ssl
import sys
import threading
import time
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qsl

here = os.path.dirname(os.path.abspath(__file__))
_conns = [0]
_lock = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def setup(self):
        super().setup()
        with _lock:
            _conns[0] += 1
            self.conn_no = _conns[0]

    def log_message(self, *args):
        pass

    def _send(self, status, body, ctype="application/json", headers=()):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        for k, v in headers:
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, obj, status=200, headers=()):
        self._send(status, json.dumps(obj, sort_keys=True).encode(), "application/json", headers)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    def _describe(self):
        parts = urlsplit(self.path)
        body = self._body()
        ctype = self.headers.get("Content-Type") or ""
        text = body.decode("utf-8", "replace")
        if ctype.startswith("multipart/form-data; boundary="):
            boundary = ctype.split("=", 1)[1]
            text = text.replace(boundary, "BOUNDARY")
            ctype = "multipart/form-data; boundary=BOUNDARY"
        return {"method": self.command, "path": parts.path, "args": "&".join(k + "=" + v for k, v in parse_qsl(parts.query, True)),
                "content-type": ctype, "content-length": self.headers.get("Content-Length") or "",
                "x-test": self.headers.get("X-Test") or "", "authorization": self.headers.get("Authorization") or "",
                "cookie": self.headers.get("Cookie") or "", "accept-encoding": self.headers.get("Accept-Encoding") or "",
                "body": text, "conn": str(self.conn_no)}

    def handle_any(self):
        parts = urlsplit(self.path)
        path = parts.path
        q = dict(parse_qsl(parts.query, True))
        seg = path.strip("/").split("/")
        if seg[0] in ("get", "anything", "post", "put", "patch", "delete", "", "a", "b"):
            self._json(self._describe())
        elif seg[0] == "status":
            self._body()
            self._send(int(seg[1]), b"", "text/plain")
        elif seg[0] == "redirect" and len(seg) == 2:
            n = int(seg[1])
            self._send(302, b"", "text/plain", [("Location", "/get" if n <= 1 else "/redirect/" + str(n - 1))])
        elif seg[0] == "redirect-to":
            self._body()
            self._send(int(q.get("status", "302")), b"", "text/plain", [("Location", q["url"])])
        elif seg[0] == "cookies" and len(seg) == 2 and seg[1] == "set":
            self._send(302, b"", "text/plain", [("Set-Cookie", k + "=" + v + "; Path=/") for k, v in q.items()] + [("Location", "/cookies")])
        elif seg[0] == "cookies" and len(seg) == 2 and seg[1] == "delete":
            self._send(302, b"", "text/plain", [("Set-Cookie", k + "=; Max-Age=0; Path=/") for k in q] + [("Location", "/cookies")])
        elif seg[0] == "cookies":
            self._json({"cookie": self.headers.get("Cookie") or ""})
        elif seg[0] == "basic-auth":
            want = "Basic " + base64.b64encode((seg[1] + ":" + seg[2]).encode()).decode()
            if self.headers.get("Authorization") == want:
                self._json({"authenticated": "yes", "user": seg[1]})
            else:
                self._send(401, b"", "text/plain", [("WWW-Authenticate", 'Basic realm="Fake Realm"')])
        elif seg[0] == "gzip":
            self._send(200, gzip.compress(json.dumps({"gzipped": "yes", "method": self.command}).encode()), "application/json", [("Content-Encoding", "gzip")])
        elif seg[0] == "deflate":
            self._send(200, zlib.compress(json.dumps({"deflated": "yes", "method": self.command}).encode()), "application/json", [("Content-Encoding", "deflate")])
        elif seg[0] == "stream":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            for i in range(int(seg[1])):
                line = ("line " + str(i) + "\n").encode()
                self.wfile.write(b"%x\r\n%s\r\n" % (len(line), line))
            self.wfile.write(b"0\r\n\r\n")
        elif seg[0] == "bytes":
            self._send(200, bytes(i % 256 for i in range(int(seg[1]))), "application/octet-stream")
        elif seg[0] == "delay":
            time.sleep(float(seg[1]))
            self._json({"delayed": seg[1]})
        elif seg[0] == "latin1":
            self._send(200, "<p>café</p>".encode("latin-1"), "text/html; charset=iso-8859-1")
        elif seg[0] == "numbers":
            self._json({"a": [1, 2], "b": [3]})
        elif seg[0] == "bad-json":
            self._send(200, b"{not json", "application/json")
        elif seg[0] == "links":
            self._send(200, b"", "text/plain", [("Link", '<https://x.test/p2>; rel="next", <https://x.test/p9>; rel="last"')])
        elif seg[0] == "multi":
            self._send(200, b"ok", "text/plain", [("Set-Cookie", "m1=one; Path=/"), ("Set-Cookie", "m2=two; Path=/"), ("X-Multi", "a"), ("X-Multi", "b")])
        else:
            self._body()
            self._send(404, b"no such page", "text/plain")

    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = do_HEAD = do_OPTIONS = handle_any


def serve(server):
    server.serve_forever()


plain = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
secure = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ctx.load_cert_chain(os.path.join(here, "..", "ssl", "cert.pem"), os.path.join(here, "..", "ssl", "key.pem"))
secure.socket = ctx.wrap_socket(secure.socket, server_side=True)
plain.daemon_threads = secure.daemon_threads = True
print(plain.server_address[1], secure.server_address[1], flush=True)
threading.Thread(target=serve, args=(secure,), daemon=True).start()
serve(plain)
