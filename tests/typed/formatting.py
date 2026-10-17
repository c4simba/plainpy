# str.format, f-string specs, % formatting, format(), hex/bin/oct, and friends
name = "Ann"
n = 42
pi = 3.14159265
print("{} is {} years".format(name, n), "{1}-{0}".format("a", "b"), "{who}!".format(who="hey"))
print("[{:>8}] [{:<8}] [{:^8}] [{:*^9}] [{:08.3f}] [{:+d}] [{:,}]".format("r", "l", "c", "mid", pi, n, 1234567))
print(f"[{name:>6}] [{name:<6}] [{name:^7}] [{n:5}] [{n:<5}] [{n:05}] [{pi:.2f}] [{pi:10.4f}] [{n:x}] [{n:#x}] [{n:b}] [{n:o}]")
print(f"{0.25:.1%} {1e-5:.2e} {12345.678:.3e} {pi:g} {1234567.0:g} {n:,} {-1234567:,} {3.0:.2}")
print(f"{'left':<10}|{'right':>10}|{'mid':^10}|")
print("%5d|%-5d|%05d|%+d|%x|%X|%o|%e|%.3g" % (n, n, n, n, 255, 255, 8, 12345.678, 0.000123456))
print(format(255, "x"), format(3.5, ".3f"), format("s", ">4"), format(7, "03"))
print(hex(255), hex(-255), bin(5), oct(8), hex(0))
print("abc".ljust(6, "."), "abc".rjust(6), "abc".center(7, "-"), "42".zfill(5), "-42".zfill(5))
print("hello world".title(), "Hello World".swapcase(), "a-b-c".rfind("-"), "abc".rfind("z"))
print("line1\nline2\n".splitlines(), "".splitlines(), "no newline".splitlines())
print(any([0, 0, 1]), any([]), all([1, 2, 3]), all([1, 0]), all([]), any(x > 2 for x in [1, 2, 3]))
print(list(reversed([1, 2, 3])), list(reversed("abc")), sum(x * x for x in range(4)), max(len(w) for w in ["a", "bbb"]))
print(pow(2, 10), pow(2.0, 0.5), pow(3, 4, 5), pow(-2, 3, 7))
for i in reversed(range(3)):
    print(i, end=" ")
print()
for i in reversed(range(2, 5)):
    print(i, end=" ")
for w in reversed(["x", "y"]):
    print(w, end=" ")
print()
print('%.5d' % -42, '%.5d' % 42, '%+.5d' % 42, '%.0d' % 0, '%.5x' % 42, '%#.5x' % -42, '%08.5d' % -42, '%-8.5d|' % 42, '%#.6o' % 8, '%.3X' % 255, '%.4d' % 3.7, '%10.5d|' % -42)   # a precision on an int: at least that many digits
# "*": the width / precision from the arguments (a negative width: left; a negative precision: 0)
sw: int = -6
sp: int = 2
spair: tuple[int, int] = (7, 42)
print(repr('%*d|' % (sw, 5)), repr('%0*d|' % (sw, 5)), repr('%.*d' % (-3, 42)), repr('%.*f' % (-3, 1.5)), repr('%.*s' % (-2, 'abc')), repr('%.*e' % (-1, 1.5)), repr('%.*g' % (-1, 1.5)))
print(repr('%*s|' % (-5, 'ab')), repr('%-*d|' % (6, 5)), repr('%*.*f|' % (8, sp, 3.14159)), repr('%.*d|' % (sp, -5)), repr('%*d|' % spair), repr('%.*x' % (4, 255)), repr('%*.*s|' % (6, 3, 'héllo')), repr('%#*x|' % (8, 255)), repr('%+*d|' % (6, 5)))
