# bytearray: everything that makes one, copies it or makes bytes of it - the
# constructors, slices, + and *, bytes(b), the comparisons and `in` (which
# compare bytes made of it), the methods that read it through bytes(b),
# printing - each round, in a field, a list and a dict; and zlib, whose
# inflate fills one (compress, decompress whole and in pieces, the checksums).
# The blocks still live at the end must not depend on the number of rounds.
import sys
import zlib


class Holder:
    def __init__(self) -> None:
        self.data = bytearray()


def round_(i: int, keep: dict[str, bytearray]) -> int:
    b = bytearray(b"hello")
    b += b", world"
    b += bytearray(b"!")
    b.extend([1, 2, 3])
    b.extend(bytes(4))
    b.append(i % 256)
    b.insert(0, 7)
    b[1] = 72
    b[2:4] = b"EL"
    b[0:1] = bytearray(b"<<")
    del b[0]
    del b[-3:]
    c = b[1:9] + b"x" + bytearray(b"y")
    d = c * 2
    s = bytes(d) + bytearray(b"z")
    n = len(s) + len(d) + d.count(b"x") + d.find(120) + (1 if b"EL" in b else 0) + (1 if 72 in b else 0)
    n += 1 if b == bytearray(b"hELlo, world!") else 0
    n += 1 if c != d else 0
    n += len(b.decode("latin-1")) + len(b.hex()) + (1 if b.startswith(b"hE") else 0)
    n += sum(c) + len(list(c)) + len(str(c)) + len(repr([c, d]))
    h = Holder()
    h.data += c
    h.data.extend(d)
    xs = [bytearray(i % 7), h.data.copy(), bytearray([1, 2])]
    keep["last"] = xs[1]
    for x in d:
        n += x
    n += d.pop() + d.pop(0)
    d.remove(d[0])
    d.reverse()
    d.clear()
    z = zlib.compress(bytes(c) * 50, 6)
    n += len(zlib.decompress(z)) + zlib.crc32(z) % 7 + zlib.adler32(z) % 7
    do = zlib.decompressobj()
    for k in range(0, len(z), 13):
        n += len(do.decompress(z[k:k + 13]))
    n += len(do.flush())
    return n + len(xs)


rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 10
keep: dict[str, bytearray] = {}
total = 0
for i in range(rounds):
    total += round_(i, keep)
print(total > 0, len(keep["last"]))
