#!/usr/bin/env python2
# -*- coding: utf-8 -*-




def validate(arch):
    valid = ('alpha',
             'amd64',
             'arm',
             'cris',
             'i386',
             'm68k',
             'mips',
             'powerpc',
             'thumb')
    assert arch in valid, "arch must be one of %r" % (valid,)
