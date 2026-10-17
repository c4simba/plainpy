# Formatting floats with a large precision, and large widths / precisions in
# "%" formatting: the text is as long as asked (a fixed buffer overran once),
# and an absurd width or precision is a ValueError, not a crash.
print(len(format(1.5, '.600')), format(1.5, '.600'))
print(len(format(1.0, '.600%')), format(1.0, '.600%')[:8], format(1.0, '.600%')[-3:])
print(len('%.600f' % 1.0), len('%.600e' % 1.5), len(format(1e300, '.600')))
print(format(1e-300, '.600')[:12], format(2.5, '.700'), format(1e22, '.800'), format(1e22, '#.700')[-3:])
print('%.5d' % -42, '%.100d' % 7, '%08.3f' % -3.14159, '%.*f' % (3, 2.0), '%*d|' % (-6, 5))
print(format(123456.789, '.3'), format(0.000012345, '.3'), format(1e300, '.3'), format(float('inf'), '.600%'))
for s in ("format(1.5, '.99999999999')", "format(2, '.99999999999f')"):
    try:
        eval(s)
        print(s, 'no error')
    except ValueError as e:
        print(s, '->', 'ValueError')
print('%.5d' % -42, '%.5d' % 42, '%+.5d' % 42, '%.0d' % 0, '%.5x' % 42, '%#.5x' % -42, '%08.5d' % -42, '%-8.5d|' % 42, '%#.6o' % 8, '%.3X' % 255, '%.4d' % 3.7, '%10.5d|' % -42)   # a precision on an int: at least that many digits
print('%.5d' % -42, '%.5d' % 42, '%+.5d' % 42, '%.0d' % 0, '%.5x' % 42, '%#.5x' % -42, '%08.5d' % -42, '%-8.5d|' % 42, '%#.6o' % 8, '%.3X' % 255, '%.4d' % 3.7, '%10.5d|' % -42)   # a precision on an int: at least that many digits
# "*": the width / precision from the arguments (a negative width: left; a negative precision: 0)
sw: int = -6
sp: int = 2
spair: tuple[int, int] = (7, 42)
print(repr('%*d|' % (sw, 5)), repr('%0*d|' % (sw, 5)), repr('%.*d' % (-3, 42)), repr('%.*f' % (-3, 1.5)), repr('%.*s' % (-2, 'abc')), repr('%.*e' % (-1, 1.5)), repr('%.*g' % (-1, 1.5)))
print(repr('%*s|' % (-5, 'ab')), repr('%-*d|' % (6, 5)), repr('%*.*f|' % (8, sp, 3.14159)), repr('%.*d|' % (sp, -5)), repr('%*d|' % spair), repr('%.*x' % (4, 255)), repr('%*.*s|' % (6, 3, 'héllo')), repr('%#*x|' % (8, 255)), repr('%+*d|' % (6, 5)))
