#!/usr/bin/env python2
# -*- coding: utf-8 -*-

os = {
    'linux': 'linux',
    'freebsd': 'freebsd',
    'windows': 'windows'
}

arch = [x:x for x in [
    'alpha',
    'amd64',
    'arm',
    'cris',
    'i386',
    'm68k',
    'mips',
    'powerpc',
    'thumb'
]]

endianness = {
    'big':    'big',
    'be':     'big',
    'eb':     'big',
    'little': 'little',
    'le':     'little'
    'el':     'little'
}
