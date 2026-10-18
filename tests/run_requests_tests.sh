#!/bin/sh
# requests (lib/requests/): tests/requests/client.py against tests/requests/server.py (CPython's
# http.server, over HTTP and TLS) - plainpy's interpreter and a compiled program must print
# tests/requests/client.out, what CPython with the real requests prints (when it has requests,
# that is checked too: the expected output is still CPython's).
#
# Environment: PLAINPY (./plainpy), PYTHON (python3), OUT (build/requests), TARGET of the compiled
# program (macos on a Mac, linux elsewhere - i386: it needs libssl3:i386; none: the interpreter
# only), FASM.
PLAINPY=${PLAINPY:-./plainpy}
PYTHON=${PYTHON:-python3}
OUT=${OUT:-build/requests}
if [ -z "$TARGET" ]; then
    if [ "$(uname -s)" = Darwin ]; then TARGET=macos; else TARGET=linux; fi
fi
FASM=${FASM:-fasm}
mkdir -p "$OUT"
pass=0; fail=0
check() {                        # name, expected file, got file
    if cmp -s "$2" "$3"; then pass=$((pass+1)); echo "PASS  $1"
    else fail=$((fail+1)); echo "FAIL  $1"; diff "$2" "$3" | head -20; fi
}

rm -f "$OUT/server.ports"
"$PYTHON" tests/requests/server.py > "$OUT/server.ports" 2>"$OUT/server.err" &
server=$!
trap 'kill $server 2>/dev/null' EXIT
i=0; while [ $i -lt 75 ] && ! [ -s "$OUT/server.ports" ]; do sleep 0.2; i=$((i+1)); done
read http_port https_port < "$OUT/server.ports"
case "$https_port" in ''|*[!0-9]*) echo "the HTTP server of $PYTHON did not start:"; cat "$OUT/server.ports" "$OUT/server.err"; exit 1;; esac

if "$PYTHON" -c "import requests" 2>/dev/null; then
    PYTHONWARNINGS=ignore "$PYTHON" tests/requests/client.py "$http_port" "$https_port" > "$OUT/client.cpython" 2>&1
    check "client (CPython, requests)" tests/requests/client.out "$OUT/client.cpython"
fi
"$PLAINPY" tests/requests/client.py "$http_port" "$https_port" > "$OUT/client.got" 2>&1
check "client (interpreter)" tests/requests/client.out "$OUT/client.got"
if [ "$TARGET" != none ]; then
    if "$PLAINPY" --compile --target "$TARGET" --fasm "$FASM" tests/requests/client.py -o "$OUT/client" > "$OUT/client.log" 2>&1; then
        "$OUT/client" "$http_port" "$https_port" > "$OUT/client.cgot" 2>&1
        check "client ($TARGET)" tests/requests/client.out "$OUT/client.cgot"
    else fail=$((fail+1)); echo "FAIL  client ($TARGET): not compiled"; cat "$OUT/client.log"; fi
fi
echo "requests tests: $pass passed, $fail failed"
[ $fail -eq 0 ]
