Getting Started
========================

To get your feet wet with pwntools, let's first go through a few examples.

Getting Acquainted
------------------------

When writing exploits, pwntools generally follows the "kitchen sink" approach.

    >>> from pwn import *

This imports a lot of functionality into the global namespace.  You can now
assemble, disassemble, pack, unpack, and many other things with a single function.

Let's start with a few common examples.


Making Connections
^^^^^^^^^^^^^^^^^^

You need to talk to the challenge binary in order to pwn it, right?
pwntools makes this stupid simple with its :mod:`pwnlib.tubes` module.

This exposes a standard interface to talk to processes, sockets, serial ports,
and all manner of things, along with some nifty helpers for common tasks.

    >>> conn = remote('google.com', 80)
    >>> conn.send('GET /404\r\n\r\n')
    >>> conn.recvline()
    'HTTP/1.0 404 Not Found\r'
    >>> conn.recvuntil(['GMT'])
    'Date: Tue, 14 Oct 2014 12:04:25 GMT'


Packing Integers
^^^^^^^^^^^^^^^^

A common task for exploit-writing is converting between integers as Python
sees them, and their representation as a sequence of bytes.
Usually folks resort to the built-in ``struct`` module.

    >>> import struct
    >>> struct.pack('I', 0xdeadbeef)
    '\xef\xbe\xad\xde'
    >>> struct.unpack('I', '7\x13\x00\x00')[0] == 0x1337
    True

pwntools makes this easier

    >>> p32(0xdeadbeef)
    '\xef\xbe\xad\xde'
    >>> u32('7\x13\x00\x00') == 0x1337
    True

The packing/unpacking operations are defined for many common bit-widths.
