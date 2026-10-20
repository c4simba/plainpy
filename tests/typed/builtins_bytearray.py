# bytearray in compiled code: made (empty, zeros, from bytes, a bytearray, a
# list of ints, a str and its encoding), changed in place (an item, a slice,
# append, extend, +=, insert, pop, remove, del, clear, reverse), read (len,
# items, slices, iteration, in, find, count, index, startswith, decode, hex)
# and compared, joined, printed; bytes() of it; a bytearray as a field, in a
# list, a function's parameter; the errors CPython raises.
b = bytearray()
print(b, len(b), bool(b), repr(b))
b.append(104)
b.extend(b"ello")
b += b", "
b += bytearray(b"world")
b.extend([33, 10])
print(b, len(b), bool(b))
print(b[0], b[-1], b[1:5], b[::3], b[-3:], b[100:])
print(bytes(b), bytes(b[:5]), b.decode().strip(), b[:5].decode("ascii"))
print(b.hex(), b[:3].hex())
z = bytearray(4)
print(z, bytearray(b"abc"), bytearray([1, 2, 255]), bytearray("héllo", "utf-8"), bytearray(z))
c = bytearray(b"hello world")
c[0] = 72
c[-1] = ord("D")
print(c)
c[6:11] = b"There"
print(c)
c[0:5] = bytearray(b"Hi")
print(c, len(c))
del c[0]
del c[-1]
print(c)
del c[1:3]
print(c)
c.insert(0, 120)
c.insert(100, 121)
c.insert(-1, 122)
print(c)
print(c.pop(), c.pop(0), c)
c.remove(122)
print(c)
c.reverse()
print(c)
d = c.copy()
d.append(0)
print(c, d, c == d, c != d, d[:-1] == c)
c.clear()
print(c, len(c), c == bytearray(), c == b"")
s = bytearray(b"abracadabra")
print(97 in s, 120 in s, b"cad" in s, b"cab" in s)
print(s.find(b"cad"), s.find(b"zzz"), s.find(98), s.count(b"a"), s.count(97), s.index(b"bra"), s.index(100))
print(s.startswith(b"abra"), s.endswith(b"bra"), s.endswith(b"x"))
total = 0
for x in s:
    total += x
print(total, list(s[:4]), sum(s), max(s), min(s))
print(s + b"!", s + bytearray(b"?"), b"<" + bytes(s) + b">", s * 2, len(s * 0))
print(s == b"abracadabra", s == bytearray(b"abracadabra"), b"abracadabra" == bytes(s))
print(str(s), f"[{s}]", "%s" % s)
w = bytearray(3)
for i in range(3):
    w[i] = 65 + i
print(w, w.decode())

class Buf:
    def __init__(self) -> None:
        self.data = bytearray()
    def put(self, chunk: bytes) -> None:
        self.data += chunk
    def take(self, n: int) -> bytes:
        out = bytes(self.data[:n])
        del self.data[:n]
        return out

q = Buf()
q.put(b"abc")
q.put(b"defgh")
print(q.take(2), q.take(4), q.data, len(q.data))
arrs: list[bytearray] = [bytearray(b"x"), bytearray(b"yy")]
arrs[0].append(120)
print(arrs, [len(a) for a in arrs])

def grow(a: bytearray, n: int) -> None:
    for i in range(n):
        a.append(i % 256)

g = bytearray()
grow(g, 100000)
print(len(g), g[99999], g[255], g[256], sum(g) % 1000)
big = bytearray(b"ab") * 3
alias = big
alias += b"!"
print(big, alias is big)
for bad in [256, -1]:
    try:
        bytearray().append(bad)
    except ValueError as e:
        print("ValueError:", e)
try:
    bytearray(b"ab")[5]
except IndexError as e:
    print("IndexError:", e)
try:
    bytearray(b"ab")[5] = 1
except IndexError as e:
    print("IndexError:", e)
try:
    bytearray().pop()
except IndexError as e:
    print("IndexError:", e)
try:
    bytearray(b"ab").remove(99)
except ValueError as e:
    print("ValueError:", e)
try:
    bytearray([300])
except ValueError as e:
    print("ValueError:", e)
