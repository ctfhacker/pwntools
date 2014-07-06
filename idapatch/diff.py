#!/usr/bin/env python
import argparse

def build_patch(a, b):
    """Builds a patch for two input strings.

    >>> a = "Hola mundo!"
    >>> b = "Hello world"
    >>> print build_patch(a,b)
    00000001: 6F 65
    00000003: 61 6C
    00000004: 20 6F
    00000005: 6D 20
    00000006: 75 77
    00000007: 6E 6F
    00000008: 64 72
    00000009: 6F 6C
    0000000A: 21 64
    """
    a = list(a)
    b = list(b)
    res = []

    if len(a) != len(b):
        raise Exception("input sizes must match")

    for i,(l,r) in enumerate(zip(a,b)):
        if l != r:
            res.append("%08X: %02X %02X" % (i, ord(l), ord(r)))
    return '\n'.join(res)
