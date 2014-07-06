import argparse, fileinput, re, binascii, struct, sys

unhex   = binascii.unhexlify
u32     = lambda x: struct.unpack('>L', x)[0]
hexa    = r'[0-9A-F]'
pattern = r'(%s{8}): (%s{2}) (%s{2})' % (hexa, hexa, hexa)
regex   = re.compile(pattern)

def apply_patch(data, patch):
    """Applies a patch to data

    Args:
        data:  List of bytes to patch
        patch: Buffer of patch data, in the format generated by IDA Pro.

    Returns:
        Patched list of bytes

    >>> orig ='Hello, world'
    >>> patch='0000000B: 64 44'
    >>> result=apply_patch(orig, patch)
    >>> result
    'Hello, worlD'
    """

    data = list(data)

    for line in patch.splitlines():
        match = regex.match(line)

        if not match:
            continue

        offset, old, new = match.groups(line)
        offset = u32(unhex(offset))
        old    = unhex(old)
        new    = unhex(new)

        # print "%08x: %r %r" % (offset, old, new)

        cur    = data[offset]
        if cur != old:
            print "ERROR! Offset %x doesn't match (expected %r, got %r)" % (offset, old, cur)
            return None

        data[offset] = new

    return ''.join(data)