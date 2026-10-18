# requests on KolibriOS (plainpy's over its sockets and mbedtls.obj), compiled and run there by
# tests/run_kolibri_requests_tests.sh against tests/requests/server.py (CPython, on the host: 10.0.2.2
# in QEMU's user network). What it finds goes to /hd0/1/kout.txt, compared with tests/requests/kolibri.out.
import sys
import requests

HERE = "/hd0/1/"


def log(s: str) -> None:
    f = open(HERE + "kout.txt", "a")
    f.write(s + "\n")
    f.close()


def first(url: str) -> requests.Response:
    """The first request: tried again while the network (DHCP, started at boot) is not up yet."""
    for attempt in range(60):
        try:
            return requests.get(url, params={"from": "kolibrios"}, headers={"X-Test": "kos"}, timeout=10)
        except requests.ConnectionError:
            sys.syscall(5, 100)
    return requests.get(url, timeout=10)


f = open(HERE + "port.txt", "r")
ports = f.read().split()
f.close()
host = "10.0.2.2"
base = "http://" + host + ":" + ports[0]
tls = "https://" + host + ":" + ports[1]
sys.syscall(5, 1000)

r = first(base + "/get")
d: dict[str, str] = r.json()
log("get: " + str(r.status_code) + " " + r.reason + " " + d["args"] + " " + d["x-test"] + " " + r.headers["content-type"])
d = requests.post(base + "/post", json={"a": [1, 2], "k": "v"}).json()
log("post json: " + d["content-type"] + " " + d["body"])
d = requests.post(base + "/post", data={"field": "value"}).json()
log("post form: " + d["body"])
r = requests.get(base + "/redirect/2")
log("redirect: " + str(r.status_code) + " " + str([h.status_code for h in r.history]))
r = requests.get(base + "/status/404")
try:
    r.raise_for_status()
except requests.HTTPError as e:
    log("HTTPError: " + str(e).replace(ports[0], "PORT"))
with requests.Session() as s:
    c: dict[str, str] = s.get(base + "/cookies/set?kos=1").json()
    log("cookies: " + c["cookie"] + " " + str(s.cookies.get_dict()))
    a: dict[str, str] = s.get(base + "/get").json()
    b: dict[str, str] = s.get(base + "/get").json()
    log("keep-alive: " + str(a["conn"] == b["conn"]))
g: dict[str, str] = requests.get(base + "/gzip").json()
log("gzip: " + g["gzipped"])
r = requests.get(base + "/stream/3", stream=True)
log("lines: " + str([line for line in r.iter_lines()]))
r = requests.get(base + "/basic-auth/k/os", auth=("k", "os"))
log("auth: " + str(r.status_code))
try:
    requests.get(base + "/delay/3", timeout=1)
    log("timeout: none")
except requests.Timeout:
    log("timeout: ReadTimeout")

t: dict[str, str] = requests.get(tls + "/get", params={"over": "tls"}, verify=False).json()
log("https: " + t["args"])
with requests.Session() as s:
    s.verify = False
    t1: dict[str, str] = s.get(tls + "/get").json()
    t2: dict[str, str] = s.post(tls + "/post", data="tls body").json()
    log("https session: " + t2["method"] + " " + t2["body"] + " " + str(t1["conn"] == t2["conn"]))
try:
    requests.get(tls + "/get", verify=HERE + "cert.pem")
    log("host name: accepted")
except requests.exceptions.SSLError:
    log("host name: SSLError")
try:
    requests.get(tls + "/get")
    log("no CAs: accepted")
except requests.exceptions.SSLError:
    log("no CAs: SSLError")
log("done")
