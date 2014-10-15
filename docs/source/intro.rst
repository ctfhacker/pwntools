.. testsetup:: *

   from pwn import *

Getting Started
========================

To get your feet wet with pwntools, let's first go through a few examples.

When writing exploits, pwntools generally follows the "kitchen sink" approach.

    >>> from pwn import *

This imports a lot of functionality into the global namespace.  You can now
assemble, disassemble, pack, unpack, and many other things with a single function.

Let's start with a few common examples.


Making Connections
------------------

You need to talk to the challenge binary in order to pwn it, right?
pwntools makes this stupid simple with its :mod:`pwnlib.tubes` module.

This exposes a standard interface to talk to processes, sockets, serial ports,
and all manner of things, along with some nifty helpers for common tasks.
For example, remote connections via :mod:`pwnlib.tubes.remote`.

.. doctest:: intro_conn

    >>> conn = remote('ftp.debian.org',21)
    >>> conn.recvline()
    '220 ftp.debian.org FTP server\r\n'
    >>> conn.send('USER anonymous\r\n')
    >>> conn.recvuntil(' ', drop=True)
    '331'
    >>> conn.recvline()
    'Please specify the password.\r\n'
    >>> conn.close()

Interacting with processes is easy thanks to :mod:`pwnlib.tubes.process`.

.. doctest:: intro_proc

    >>> sh = process('/bin/sh')
    >>> sh.sendline('sleep 3; echo hello world;')
    >>> sh.recvline(timeout=1)
    ''
    >>> sh.recvline(timeout=5)
    'hello world\n'
    >>> sh.close()

Not only can you interact with processes programmatically, but you can
actually **interact** with processes.

    >>> sh.interactive() # doctest: +SKIP
    $ whoami
    user

There's even an SSH module for when you've got to SSH into a box to perform
a local/setuid exploit with :mod:`pwnlib.tubes.ssh`.  You can quickly spawn
processes and grab the output, or spawn a process and interact iwth it like
a ``process`` tube.

.. doctest:: intro_shell

    >>> shell = ssh('bandit0', 'bandit.labs.overthewire.org', password='bandit0')
    >>> shell['whoami']
    'bandit0'
    >>> shell.download_file('/etc/motd')
    >>> sh = shell.run('sh')
    >>> sh.sendline('sleep 3; echo hello world;')
    >>> sh.recvline(timeout=1)
    ''
    >>> sh.recvline(timeout=5)
    'hello world\n'

Packing Integers
------------------

A common task for exploit-writing is converting between integers as Python
sees them, and their representation as a sequence of bytes.
Usually folks resort to the built-in ``struct`` module.

pwntools makes this easier with :mod:`pwnlib.util.packing`.  No more remembering
unpacking codes, and littering your code with helper routines.

    >>> import struct
    >>> p32(0xdeadbeef) == struct.pack('I', 0xdeadbeef)
    True
    >>> leet = '37130000'.decode('hex')
    >>> u32('abcd') == struct.unpack('I', 'abcd')[0]
    True

The packing/unpacking operations are defined for many common bit-widths.

    >>> u8('A') == 0x41
    True

Assembly and Disassembly
------------------------

Never again will you need to run some already-assembled pile of shellcode
from the internet!  The :mod:`pwnlib.asm` module is full of awesome.

    >>> asm('mov eax, 0').encode('hex')
    'b800000000'

But if you do, it's easy to suss out!

    >>> print disasm('6a0258cd80ebf9'.decode('hex'))
       0:   6a 02                   push   0x2
       2:   58                      pop    eax
       3:   cd 80                   int    0x80
       5:   eb f9                   jmp    0x0

However, you shouldn't even need to write your own shellcode most of the
time!  Pwntools comes with the :mod:`pwnlib.shellcraft` module, which is
loaded with useful time-saving shellcodes.

Let's say that we want to `setreuid(getuid(), getuid())` followed by `dup`ing
file descriptor 4 to `stdin`, `stdout`, and `stderr`, and then pop a shell!

    >>> asm(shellcraft.setreuid() + shellcraft.dupsh(4)).encode('hex')
    '6a3158cd8089c389c16a4658cd806a045b6a0359496a3f58cd8075f831c9f7e96a01fe0c24682f2f7368682f62696eb00b89e3cd80'

Misc Tools
----------------------

Never write another hexdump, thanks to :mod:`pwnlib.util.fiddling`.


Find offsets in your buffer that cause a crash, thanks to :mod:`pwnlib.cyclic`.

    >>> print cyclic(20)
    aaaabaaacaaadaaaeaaa
    >>> # Assume EIP = 0x62616166 ('faab') at crash time
    >>> print cyclic_find('faab')
    120

ELF Manipulation
-------------

Stop hard-coding things!  Look them up at runtime with :mod:`pwnlib.elf`.

    >>> e = ELF('/bin/cat')
    >>> print hex(e.address) #doctest: +SKIP
    0x400000
    >>> print hex(e.symbols['write']) #doctest: +SKIP
    0x401680
    >>> print hex(e.got['write']) #doctest: +SKIP
    0x60b070
    >>> print hex(e.plt['write']) #doctest: +SKIP
    0x401680

You can even patch and save the files.

    >>> e = ELF('/bin/cat')
    >>> e.read(e.address+1, 3)
    'ELF'
    >>> e.asm(e.address, 'ret')
    >>> e.save('/tmp/quiet-cat')
    >>> disasm(file('/tmp/quiet-cat','rb').read(1))
    '   0:   c3                      ret'

