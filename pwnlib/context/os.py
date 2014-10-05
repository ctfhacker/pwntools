#!/usr/bin/env python2
# -*- coding: utf-8 -*-

valid = 'linux', 'freebsd', 'windows'

def validate(os):
    assert os in valid, "os must be one of %r" % (valid,)
