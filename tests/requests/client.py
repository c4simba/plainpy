# requests against tests/requests/server.py: the same output from CPython with the real requests,
# plainpy's interpreter and compiled programs (tests/run_requests_tests.sh). argv: the HTTP port,
# the HTTPS port.
import sys
import requests
from requests.auth import HTTPBasicAuth

http_port = sys.argv[1]
https_port = sys.argv[2]
base = "http://127.0.0.1:" + http_port
tls = "https://localhost:" + https_port
cafile = "tests/ssl/cert.pem"


def clean(s: str) -> str:
    return s.replace(http_port, "PORT").replace(https_port, "TPORT")


def show(d: dict[str, str], *keys: str) -> None:
    print("  " + ", ".join(k + "=" + repr(d[k]) for k in keys))


# GET, params, the response
r = requests.get(base + "/get", params={"q": "a b", "n": "1"}, headers={"X-Test": "yes"}, timeout=5)
print(r, r.status_code, r.reason, r.ok, bool(r), r.encoding, clean(r.url))
print(r.headers["content-type"], "Content-Type" in r.headers, r.headers.get("x-nothing"), r.headers.get("x-nothing", "dflt"))
d: dict[str, str] = r.json()
show(d, "method", "path", "args", "x-test", "accept-encoding", "body")
print(len(r.content) > 0, r.text == r.content.decode(), clean(r.request.url), r.request.method, r.request.headers["X-Test"])
print(r.elapsed.total_seconds() >= 0, r.history, r.is_redirect, r.links)

# a list of pairs, a str, a list value
r = requests.get(base + "/get?x=0", params=[("a", "1"), ("a", "2")])
d = r.json()
show(d, "args")
d = requests.get(base + "/get", params="raw=yes&z").json()
show(d, "args")
multi: dict[str, list[str] | None] = {"multi": ["1", "2"], "none": None}
d = requests.get(base + "/get", params=multi).json()
show(d, "args")

# bodies: a form, json, a str, bytes
d = requests.post(base + "/post", data={"k": "v", "e": "é"}).json()
show(d, "method", "content-type", "content-length", "body")
d = requests.post(base + "/post", json={"a": [1, 2], "b": "x"}).json()
show(d, "content-type", "body")
d = requests.put(base + "/put", data="plain text").json()
show(d, "method", "content-type", "body")
d = requests.patch(base + "/patch", data=b"\x01raw").json()
show(d, "method", "content-length")
d = requests.delete(base + "/delete").json()
show(d, "method", "content-length", "body")
d = requests.post(base + "/post").json()
show(d, "content-length")
r = requests.head(base + "/get")
print("head", r.status_code, r.content, r.headers["content-type"])
r = requests.options(base + "/anything")
print("options", r.status_code)
r = requests.request("PATCH", base + "/anything", data={"x": "1"})
dd: dict[str, str] = r.json()
show(dd, "method", "body")

# files: multipart
d = requests.post(base + "/post", files={"f": ("a.txt", b"hello", "text/plain")}, data={"field": "value"}).json()
show(d, "content-type", "body")
d = requests.post(base + "/post", files={"g": b"raw bytes"}).json()
show(d, "body")

# status codes, raise_for_status
for code in (200, 204, 404, 500):
    r = requests.get(base + "/status/" + str(code))
    try:
        r.raise_for_status()
        print(code, "ok", r.ok, repr(r.text))
    except requests.HTTPError as e:
        print(code, "HTTPError:", clean(str(e)), e.response.status_code if e.response is not None else -1)
print(requests.codes.ok, requests.codes.not_found, requests.codes.teapot, requests.codes["created"])

# redirections
r = requests.get(base + "/redirect/3")
print("redirect", r.status_code, clean(r.url), [h.status_code for h in r.history], [clean(h.url) for h in r.history])
r = requests.get(base + "/redirect/2", allow_redirects=False)
print("not followed", r.status_code, r.is_redirect, r.headers["location"], r.history)
r = requests.post(base + "/redirect-to?url=/post&status=307", data={"keep": "me"})
d = r.json()
show(d, "method", "body")
r = requests.post(base + "/redirect-to?url=/get&status=302", data={"drop": "me"})
d = r.json()
show(d, "method", "body", "content-type")
r = requests.post(base + "/redirect-to?url=/get&status=303", data="x")
d = r.json()
show(d, "method")
r = requests.get(base + "/redirect-to?url=" + base + "/get&status=301", auth=("u", "p"))
d = r.json()
show(d, "authorization")
r = requests.get(base + "/redirect-to?url=http://localhost:" + http_port + "/get", auth=("u", "p"))
d = r.json()
show(d, "authorization")
s = requests.Session()
s.max_redirects = 2
try:
    s.get(base + "/redirect/5")
except requests.TooManyRedirects as e:
    print("TooManyRedirects:", e)
s.close()

# cookies
r = requests.get(base + "/cookies", cookies={"a": "1", "b": "2"})
dc: dict[str, str] = r.json()
show(dc, "cookie")
r = requests.get(base + "/multi")
print("multi", sorted(r.cookies.keys()), r.cookies.get("m1"), r.headers["x-multi"], len(r.cookies))
with requests.Session() as s:
    r = s.get(base + "/cookies/set?sess=abc&k=v")
    dc = r.json()
    show(dc, "cookie")
    print("jar", sorted(s.cookies.keys()), s.cookies["sess"], "sess" in s.cookies, s.cookies.get_dict()["k"])
    dc = s.get(base + "/cookies").json()
    show(dc, "cookie")
    dc = s.get(base + "/cookies", cookies={"extra": "1"}).json()
    show(dc, "cookie")
    dc = s.get(base + "/cookies/delete?sess").json()
    show(dc, "cookie")
    print("after delete", sorted(s.cookies.keys()))

# sessions: headers, params, auth, keep-alive
with requests.Session() as s:
    s.headers["X-Test"] = "session"
    s.headers.update({"Accept": "application/json"})
    s.params = {"from": "session"}
    s.auth = ("user", "pass")
    r1 = s.get(base + "/get", params={"q": "1"})
    d = r1.json()
    show(d, "x-test", "args", "authorization")
    r2 = s.get(base + "/get", headers={"X-Test": "request"})
    d2: dict[str, str] = r2.json()
    show(d2, "x-test")
    print("same connection", d["conn"] == d2["conn"])
    drop: dict[str, str | None] = {"X-Test": None}            # (None: the session's header not sent)
    r3 = s.get(base + "/get", headers=drop)
    d3: dict[str, str] = r3.json()
    show(d3, "x-test")
    print(s.headers["accept"], r1.request.headers["Accept"])

# authentication
r = requests.get(base + "/basic-auth/al/pw", auth=("al", "pw"))
da: dict[str, str] = r.json()
print("basic", r.status_code, da["authenticated"], da["user"])
r = requests.get(base + "/basic-auth/al/pw", auth=HTTPBasicAuth("al", "wrong"))
print("wrong", r.status_code, r.headers["www-authenticate"])
r = requests.get("http://al:pw@127.0.0.1:" + http_port + "/basic-auth/al/pw")
print("in url", r.status_code)

# content encodings, streams
r = requests.get(base + "/gzip")
dg: dict[str, str] = r.json()
print("gzip", dg["gzipped"], r.headers["content-encoding"])
r = requests.get(base + "/deflate")
dg = r.json()
print("deflate", dg["deflated"])
r = requests.get(base + "/stream/5", stream=True)
lines = [line for line in r.iter_lines()]
print("lines", lines)
r = requests.get(base + "/bytes/1000", stream=True)
sizes = [len(c) for c in r.iter_content(256)]
print("chunks", sizes)
r = requests.get(base + "/bytes/300")
print("bytes", len(r.content), r.content[:4], r.content[-2:], len(list(r.iter_content(100))))
r = requests.get(base + "/stream/3")
print("text", repr(r.text))
with requests.get(base + "/stream/2", stream=True) as r:
    print("with", r.status_code, r.content)

# text and encodings
r = requests.get(base + "/latin1")
print("latin1", r.encoding, r.text)
r.encoding = "utf-8"
print("as utf-8", repr(r.text))
r = requests.get(base + "/links")
print("links", r.links["next"]["url"], r.links["last"]["rel"])

# JSON of other types
r = requests.get(base + "/numbers")
nums: dict[str, list[int]] = r.json()
print("numbers", nums["a"], sum(nums["b"]))
try:
    bad: dict[str, str] = requests.get(base + "/bad-json").json()
    print(bad)
except requests.JSONDecodeError as e:
    print("JSONDecodeError")

# errors
try:
    requests.get("127.0.0.1/x")
except requests.exceptions.MissingSchema as e:
    print("MissingSchema:", e)
try:
    requests.get("http:///x")
except requests.exceptions.InvalidURL as e:
    print("InvalidURL:", e)
try:
    requests.get("gopher://x/")
except requests.exceptions.InvalidSchema as e:
    print("InvalidSchema:", e)
try:
    requests.get("http://127.0.0.1:1/", timeout=3)
except requests.ConnectionError as e:
    print("ConnectionError")
try:
    requests.get(base + "/delay/3", timeout=0.5)
except requests.ReadTimeout as e:
    print("ReadTimeout")
try:
    requests.get(base + "/delay/3", timeout=(3, 0.5))
except requests.Timeout as e:
    print("Timeout")
try:
    requests.get(base + "/get", headers={"Bad": "x\r\ny"})
except requests.exceptions.InvalidHeader as e:
    print("InvalidHeader:", e)

# https
r = requests.get(tls + "/get", params={"over": "tls"}, verify=cafile)
d = r.json()
print("https", r.status_code, clean(r.url))
show(d, "args")
r = requests.get(tls + "/get", verify=False)
print("unverified", r.status_code)
try:
    requests.get(tls + "/get")
except requests.exceptions.SSLError as e:
    print("SSLError (system CAs)")
with requests.Session() as s:
    s.verify = False
    a1: dict[str, str] = s.get(tls + "/get").json()
    a2: dict[str, str] = s.post(tls + "/post", json={"t": 1}).json()
    print("tls session", a2["method"], a2["body"], a1["conn"] == a2["conn"])

# a prepared request
req = requests.Request("POST", base + "/post", data={"p": "q"}, headers={"X-Test": "prep"})
prepped = req.prepare()
print(req, prepped, prepped.method, clean(prepped.url), prepped.headers["Content-Type"])
with requests.Session() as s:
    r = s.send(prepped, timeout=5)
    d = r.json()
    show(d, "method", "x-test", "body")
    p2 = s.prepare_request(requests.Request("GET", base + "/get", params={"x": "1"}))
    print(clean(p2.url), p2.headers["User-Agent"].startswith("python-requests/"))
