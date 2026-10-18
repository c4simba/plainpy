# The interpreter's caches (attribute lookups by type, LOAD_GLOBAL, attribute hooks) and its fast
# paths for numbers and subscripts: what changes after a lookup must be seen.
import builtins


def g():
    return "g1"


def call_g():
    return g()


print(call_g())
def g():
    return "g2"
print(call_g())

def use_len(x):
    return len(x)


print(use_len([1, 2]))
len = lambda x: 42
print(use_len([1, 2]))
del len
print(use_len([1, 2, 3]))
builtins.my_extra = "from builtins"
def use_extra():
    return my_extra
print(use_extra())
builtins.my_extra = "changed"
print(use_extra())
globals()["my_extra"] = "a global first"
print(use_extra())
del globals()["my_extra"]
print(use_extra())
del builtins.my_extra
try:
    use_extra()
except NameError as e:
    print("NameError:", e)

code = compile("def h():\n    return k\n", "<x>", "exec")
for k_value in (1, 2):
    ns = {"k": k_value}
    exec(code, ns)
    print(ns["h"]())
ns2 = {"k": "other dict"}
exec("def h():\n    return k\nr = h()", ns2)
print(ns2["r"])


class A:
    def m(self):
        return "A.m"


class B(A):
    pass


b = B()
print(b.m())
A.m = lambda self: "A.m replaced"
print(b.m())
B.m = lambda self: "B.m"
print(b.m())
del B.m
print(b.m())
del A.m
try:
    b.m()
except AttributeError as e:
    print("AttributeError:", e)
A.__getattr__ = lambda self, name: "missing " + name
print(b.anything)
del A.__getattr__
try:
    b.anything
except AttributeError as e:
    print("AttributeError:", e)
log = []
A.__setattr__ = lambda self, name, v: log.append((name, v))
b.x = 1
print(log, "x" in b.__dict__)
del A.__setattr__
b.x = 2
print(b.x)
A.__getattribute__ = lambda self, name: "always " + name
print(b.x, b.y)
del A.__getattribute__
print(b.x)


for i in range(3):
    class Tmp:
        v = i

        def get(self):
            return self.v
    print(Tmp().get(), Tmp.v)

print(7 // 2, -7 // 2, 7 // -2, -7 % 3, 7 % -3, -7.5 // 2, 7.5 % 2)
print(2 ** 62 - 1 + 2 ** 62, 3 * 4, 3 * 4.5, 1 / 4, 7 / 2.0, 6 - 2.5, 1.5 + 2, 5 & 3, 5 | 3, 5 ^ 3, -16 >> 2, 1 >> 70)
try:
    print(1 / 0)
except ZeroDivisionError as e:
    print("ZeroDivisionError:", e)
try:
    print(5 % 0)
except ZeroDivisionError as e:
    print("ZeroDivisionError:", e)
try:
    print(2.0 / 0)
except ZeroDivisionError as e:
    print("ZeroDivisionError:", e)
nan = float("nan")
print(nan < 1.0, nan == nan, nan != nan, 0.1 + 0.2 == 0.3, 2.5 >= 2.5, 2 ** 53 + 1 == float(2 ** 53 + 1), 1 < 1.5, True + 1, True * 2.5)
x = 10
x += 5
x *= 2
x //= 4
x %= 5
y = 1.5
y += 1
y *= 2
print(x, y)

xs = [10, 20, 30]
t = (1, 2, 3)
d = {"a": 1, 2: "two"}
print(xs[0], xs[-1], t[1], t[-3], d["a"], d[2])
xs[1] = 21
xs[-1] = 31
d["b"] = 2
print(xs, sorted(d.items(), key=str))
for bad in (lambda: xs[3], lambda: t[-4], lambda: d["zz"], lambda: xs["a"], lambda: d[[1]]):
    try:
        bad()
    except (IndexError, KeyError, TypeError) as e:
        print(type(e).__name__ + ":", e)
try:
    xs[5] = 1
except IndexError as e:
    print("IndexError:", e)


class L(list):
    def __getitem__(self, i):
        return "L" + str(i)


class M(dict):
    def __missing__(self, k):
        return "missing " + str(k)


print(L([1, 2])[0], M()["q"], xs[True], d.get("zz"))


# __bases__ assignment: the MRO made again (the subclasses' too), what lookups cached before not used
class Base:
    pass


class C(Base):
    pass


class D(Base):
    def who(self):
        return "D"


class Sub(C):
    pass


c = C()
s = Sub()
print(hasattr(c, "who"), [k.__name__ for k in Sub.__mro__])
C.__bases__ = (D,)
print(c.who(), s.who(), [k.__name__ for k in C.__mro__], [k.__name__ for k in Sub.__mro__], C.__bases__, D.__subclasses__(), Base.__subclasses__())
for bad in ((), [D], (1,), (Sub,)):
    try:
        C.__bases__ = bad
    except TypeError as e:
        print("TypeError:", e)


class E:
    pass


try:
    E.__bases__ = (D,)
except TypeError as e:
    print("TypeError:", e)
try:
    int.__bases__ = (object,)
except TypeError as e:
    print("TypeError:", e)
C.__bases__ = (Base,)
print(hasattr(c, "who"), [k.__name__ for k in Sub.__mro__])
