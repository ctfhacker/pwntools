
INPUT='HELLO WORLD'.ljust(0x100)

def test_string():
    x = ''
    for i in range(0x1000):
        x += INPUT
        x.count('\n')
    print len(x)

def test_list():
    x = []
    for i in range(0x1000):
        x.append(INPUT)
        x.count('\n')
    print len(x)


def test_bytearray():
    x = bytearray('')
    for i in range(0x1000):
        x += INPUT
        x.count('\n')
    print len(x)

import timeit

print timeit.timeit('test_string()', setup="from __main__ import test_string", number=10)
print timeit.timeit('test_list()', setup="from __main__ import test_list", number=10)
print timeit.timeit('test_bytearray()', setup="from __main__ import test_bytearray", number=10)