#!/usr/bin/env python2
# -*- coding: utf-8 -*-

valid = ('alpha',
         'amd64',
         'arm',
         'cris',
         'i386',
         'm68k',
         'mips',
         'powerpc',
         'thumb')

def validate(arch):
    assert arch in valid, "arch must be one of %r" % (valid,)
