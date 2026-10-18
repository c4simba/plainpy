#!/bin/sh
# requests on KolibriOS, in QEMU: tests/requests/kolibri.py compiled for the kolibri target (or run
# by plainpy there: KOS_PLAINPY=<the folder of a KolibriOS build>) against tests/requests/server.py
# on this machine (10.0.2.2 in QEMU's user network). What the program writes (kout.txt) must be
# tests/requests/kolibri.out.
#
# Needs qemu-system-i386, mtools (mtype, mcopy), a KolibriOS floppy image (KOS_IMG: kolibri.img of
# builds.kolibrios.org/en_US/latest-img.7z), mbedtls.obj (TLS: make kolibri-tls) and fasm (FASM).
# OUT/hd is the VM's /hd0/1; WAIT: the seconds the VM gets (QEMU without KVM is slow).
PLAINPY=${PLAINPY:-./plainpy}
PYTHON=${PYTHON:-python3}
OUT=${OUT:-build/kolibri-requests}
FASM=${FASM:-fasm}
TLS=${TLS:-build/kolibri/mbedtls.obj}
WAIT=${WAIT:-400}
if [ ! -f "$KOS_IMG" ]; then echo "KOS_IMG=<a KolibriOS floppy image> (builds.kolibrios.org/en_US/latest-img.7z: kolibri.img)"; exit 1; fi
if [ ! -f "$TLS" ]; then echo "$TLS: not built (make kolibri-tls)"; exit 1; fi
rm -rf "$OUT"
mkdir -p "$OUT/hd"
if [ -n "$KOS_PLAINPY" ]; then
    cp "$KOS_PLAINPY/plainpy" "$KOS_PLAINPY/plainpy.lib" tests/requests/kolibri.py "$OUT/hd/"
    mkdir -p "$OUT/hd/lib" && cp -R lib/. "$OUT/hd/lib/"
    run='/hd0/1/plainpy /hd0/1/kolibri.py'
    mode=interpreter
else
    "$PLAINPY" --compile --target kolibri --fasm "$FASM" tests/requests/kolibri.py -o "$OUT/hd/ktest" > "$OUT/compile.log" 2>&1 || { cat "$OUT/compile.log"; exit 1; }
    rm -f "$OUT/hd/ktest.asm"
    run='/hd0/1/ktest ""'
    mode=compiled
fi
cp tests/ssl/cert.pem "$OUT/hd/"
cp "$TLS" "$OUT/hd/mbedtls.obj"
cp "$KOS_IMG" "$OUT/run.img"
mtype -i "$OUT/run.img" ::/SETTINGS/AUTORUN.DAT > "$OUT/autorun.dat" || exit 1
printf '%s 0\r\n' "$run" >> "$OUT/autorun.dat"
mcopy -o -i "$OUT/run.img" "$OUT/autorun.dat" ::/SETTINGS/AUTORUN.DAT || exit 1

"$PYTHON" tests/requests/server.py > "$OUT/server.ports" 2>"$OUT/server.err" &
server=$!
qemu=""
trap 'kill $server $qemu 2>/dev/null' EXIT
i=0; while [ $i -lt 75 ] && ! [ -s "$OUT/server.ports" ]; do sleep 0.2; i=$((i+1)); done
cp "$OUT/server.ports" "$OUT/hd/port.txt"
qemu-system-i386 -m 256 -drive "file=$OUT/run.img,format=raw,if=floppy" -boot a -drive "file=fat:rw:$OUT/hd,format=raw,if=ide,index=0" \
    -vga std -display none -nic "user,model=e1000" > "$OUT/qemu.log" 2>&1 &
qemu=$!
i=0; while [ $i -lt $((WAIT * 2)) ] && ! grep -q "^done" "$OUT/hd/kout.txt" 2>/dev/null; do sleep 0.5; i=$((i+1)); done
kill $qemu 2>/dev/null

if cmp -s tests/requests/kolibri.out "$OUT/hd/kout.txt"; then echo "PASS  requests (kolibrios, $mode)"; exit 0; fi
echo "FAIL  requests (kolibrios, $mode)"; diff tests/requests/kolibri.out "$OUT/hd/kout.txt" | head -30
exit 1
