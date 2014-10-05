#!/usr/bin/env python2
# -*- coding: utf-8 -*-
import types, sys, threading
from . import log_levels

# These attributes are set on the defaults module after it have been constructed
# If you change any of these values, remember to update the docstring.
defaults = {
    'endianness': 'little',
    'sign': 'unsigned',
    'word_size': 32,
    'log_level': 'error',
    '__doc__': '''The global default-version of :mod:`pwnlib.context`.

For at description see :mod:`pwnlib.context`. This is the global defaults, that
act as a "base" for the thread-local values.
'''}

# These are the possiblities for arch and os
__possible__ = {
    'arch': (
        'alpha', 'aarch64', 'amd64', 'arm', 'armeb',
        'cris', 'i386', 'm68k', 'mips',
        'mipsel', 'powerpc', 'powerpc64', 'thumb'
    ),
    'arch32': ('arm', 'armeb', 'cris', 'i386', 'm68k', 'mips', 'mipsel', 'thumb', 'powerpc'),
    'arch64': ('aarch64', 'alpha', 'amd64', 'powerpc64'),
    'os': ('linux', 'freebsd')
}

import threading
from collections import defaultdict

ContextBasicDefaults = {
    'os': 'linux',
    'arch': 'i386',
    'endian': 'little',
    'timeout': 'default'
}

def ValidateEndianness(endianness, context_dict=None):
    """ValidateEndian(endianness, context_dict=None) => str

    Validates the specified string as a valid endianness.

    Arguments:
        endianness(str): String specifying endianness
        context_dict(dict): Unused

    Returns:
        String containing endianness value

    :rasies ValueError: An invalid endianness was provided

    >>> ValidateEndianness('be')
    'big'
    >>> ValidateEndianness('little')
    'little'
    >>> ValidateEndianness('foobar')
    Traceback (most recent call last):
     ...
    ValueError: endianness must be one of ['el', 'little', 'le', 'be', 'big', 'eb']
    """

    aliases = {
        'be': 'big',
        'eb': 'big',
        'big': 'big',
        'le': 'little',
        'el': 'little',
        'little': 'little'
    }

    endianness = endianness.lower()

    if endianness not in aliases:
        raise ValueError("endianness must be one of %r" % (aliases.keys(),))

    return aliases[endianness]

def ValidateWordSize(word_size, context_dict=None):
    valid     = (16, 32, 64, 128)
    word_size = int(word_size)
    if word_size not in valid:
        raise ValueError("word_size must be one of %r" % (valid,))
    return word_size

def ValidateArch(context_dict, arch):
    """ValidateArch(context_dict, arch) => str

    Validates the specified architecture, and uses context_dict to provide
    additional hinting or default setting.

    For example, specifying `context.arch = 'mips64el' should set `context.arch`,
    `context.endianness`, and `context.word_size`.

    However, the latter two will not override  user-suppled values.

    Arguments:
        context_dict(dict): Dictionary containing context information
        arch(str):          String representation of the architecture name

    Returns:
        String representation of the architecture, after cleaning any
        additional trailing fields.

    :raises UserError: Raised if `arch` implies an additional value which the user has already specified.
    :raises ValueError: An invalid architecture was specified

    >>> ValidateArch({}, 'mips')
    'mips'
    >>> ValidateArch({}, 'doge')
    Traceback (most recent call last):
     ...
    ValueError: endianness must be one of ['el', 'little', 'le', 'be', 'big', 'eb']
    >>> ctx = {}
    >>> ValidateArch({}, 'powerpc64be')
    'powerpc'
    >>> ctx
    {'endianness': 'big', 'word_size': 64}


    """
    valid = ('alpha',
             'amd64',
             'arm',
             'cris',
             'i386',
             'm68k',
             'mips',
             'powerpc',
             'thumb')

    endian    = None
    word_size = None
    arch      = arch.lower()

    while arch not in valid:
        # Attempt to handle "mipsle" or "armeb", and override the default
        # if an explicit value has not been set.
        try:
            endianness = ValidateEndianness(arch[-2:])
            arch = arch[:-2]
            if 'endianness' not in context_dict:
                context_dict['endianness'] = endianness
            else:
                raise UserWarning("endianness specified with arch (%r); arch is already set (%r)" % (arch, endianness))
            continue
        except LookupError:
            pass

        # Attempt to handle "powerpc64" or "arm64", and override the default
        # if an explicit value has not been set.
        try:
            word_size = ValidateWordSize(arch[-2:])
            arch = arch[:-2]
            if 'word_size' not in context_dict:
                context_dict['word_size'] = word_size
            else:
                raise UserWarning("word_size specified with arch (%r); arch is already set (%r)" % (arch, word_size))
            continue
        except LookupError:
            pass

        # Raise an exception, as it's still not valid and we can't make it better
        raise LookupError('arch must be one of %r' % (valid,))

    return arch


ValidatorsAndAliases = {
    'arch': ,
    'os': { i:i for i in ('linux','freebsd','windows')},
    'endianness': ,
    'word_size': {
        32: 32,
        64: 64
    },
}
def validate_arch(x):
    valid =
    assert arch in valid, "arch must be one of %r" % (valid,)


class ContextValidator(defaultdict):
    def __init__(self):
        super(ContextValidator, self).__init__(None)

    def __missing__(self, key):
        if key in ContextBasicDefaults:
            return defaults[key]

        return ContextComputeDefault(self, key)

class TlsContextStack(threading.local):
    def __init__(self):
        # The currently-activated context, through which context.xxx is serviced
        self.current = defaultdict(lambda: None)

        # The stack of contexts which are popped on Context.__exit__
        self.stack   = []

    def push(self):
        self.stack.append(self.current.copy())

    def pop(self):
        self.current.clear()
        self.current.update(self.stack.pop())

    def __getitem__(self, k):
        return self.current[k]

    def __setitem__(self, k, v):
        self.current[k] = v


class TlsContext(object):
    __slots__ = 'tls',

    def __init__(self):
        self.tls = TlsContextStack()

    def __call__(self, **kwargs):
        for k,v in kwargs.items():
            setattr(self,k,v)
        return self

    def __repr__(self):
        v = ["%s = %r" % (k,v) for k,v in self.tls.current.items()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(v))

    def local(self, **kwargs):
        ctx = self
        class LocalContext(object):
            def __enter__(self):
                ctx.tls.push()
                ctx(**kwargs)
                return ctx

            def __exit__(self, *a, **b):
                ctx.tls.pop()

        return LocalContext()

    @property
    def arch(self):
        return self.tls['arch']
    @arch.setter
    def arch(self, value):
        self.tls['arch'] = value

    @property
    def endianness(self):
        return self.tls['endianness']

    @endianness.setter
    def endianness(self, value):
        self.tls['endianness'] = value

    @property
    def os(self):
        return self.tls['os']
    @os.setter
    def os(self, value):
        self.tls['os'] = value

    @property
    def timeout(self):
        return self.tls['timeout']
    @timeout.setter
    def timeout(self, value):
        self.tls['timeout'] = value

    @property
    def word_size(self):
        return self.tls['word_size']
    @word_size.setter
    def word_size(self, value):
        self.tls['word_size'] = value

    @property
    def endian(self):
        return self.endianness
    @endian.setter
    def endian(self, value):
        self.endianness = value

    @property
    def ptr_size(self):
        return (self.word_size or 0) / 8


defaults = {
    'os': 'voodoo'
}

context(**defaults)

class ScopedContextManager(object):
    def __init__(self, current=None):
        self.scopes = [current or ScopedContext()]

    def __setattr__(self, name, value):
        setattr(self.current(), name, value)

    def __getattr__(self, name):
        getattr(self.current(), name)

    def current(self):
        return self.contexts[0]

    def push(self, context):
        self.contexts.append(context)

    def pop(self, context=None):
        popped = self.contexts.pop()
        if context is None or context is popped:
            return popped
        raise RuntimeWarning("Popped context %r is not the same as expected %r" % (popped, context))




class ThreadLocalContextManager(object):
    def __init__(self):
        self.threads = {}

class Local(object):
    def __init__(self, args):
        self.args = args

    def __enter__(self):
        self.saved = context._thread_ctx().__dict__.copy()
        for k, v in self.args.items():
            setattr(context, k, v)

    def __exit__(self, *args):
        context._thread_ctx().__dict__.clear()
        context._thread_ctx().__dict__.update(self.saved)

def _updater(updater, name = None, doc = None):
    name = name or updater.__name__
    doc  = doc  or updater.__doc__

    def getter(self):
        if hasattr(self, '_' + name):
            return getattr(self, '_' + name)
        elif self.defaults:
            return getattr(self.defaults, name)
        else:
            return None

    def setter(self, val):
        setattr(self, '_' + name, updater(self, val))

    # Setting _inner is a slight hack only used to get better documentation
    res = property(getter, setter, doc = doc)
    res.fget._inner = updater
    return res

def _validator(validator, name = None, doc = None):
    name = name or validator.__name__
    doc  = doc  or validator.__doc__

    def updater(self, val):
        if val == None or validator(self, val):
            return val
        else:
            raise AttributeError(
                'Cannot set context-key %s to %s, did not validate' % \
                  (name, val)
            )

    # Setting _inner is a slight hack only used to get better documentation
    res = _updater(updater, name, doc)
    res.fget._inner = validator
    return res

def properties():
    keys = [k for k in dir(ContextModule) if k[0] != '_']
    return {k: getattr(ContextModule, k) for k in keys}

class ContextModule(types.ModuleType):
    def __init__(self, defaults = None):
        super(ContextModule, self).__init__(__name__)
        self.defaults     = defaults
        self.__possible__ = __possible__
        self.__dict__.update({
            '__all__'     : [],
            '__file__'    : __file__,
            '__package__' : __package__,
        })

    def __call__(self, **kwargs):
        """This function is the global equivalent of
        :func:`pwnlib.context.__call__`.

        Args:
          kwargs: Variables to be assigned in the environment."""

        for k, v in kwargs.items():
            setattr(self, k, v)

    @_validator
    def arch(self, value):
        """Variable for the current architecture. This is useful e.g. to make
        :mod:`pwnlib.shellcraft` easier to use. Allowed values:

        * ``alpha``
        * ``amd64``
        * ``arm``
        * ``armeb``
        * ``cris``
        * ``i386``
        * ``m68k``
        * ``mips``
        * ``mipsel``
        * ``powerpc``
        * ``thumb``

        Setting this will also update :data:`pwnlib.context.word_size`.
        """

        if value in self.__possible__['arch']:
            if value in self.__possible__['arch32']:
                self.word_size = 32
            elif value in self.__possible__['arch64']:
                self.word_size = 64
            return value

    @property
    def ptr_size(self):
        return self.word_size/8

    @_validator
    def os(self, value):
        """Variable for the current operating system. This is useful e.g. for
        choosing the right constants for syscall numbers.

        Allowed values:

        * ``linux``
        * ``freebsd``"""

        if value in self.__possible__['os']:
            return value

    @_validator
    def endianness(self, value):
        """The default endianness used for e.g. the
        :func:`pwnlib.util.packing.pack` function. Defaults to ``little``.

        Allowed values:

        * ``little``
        * ``big``"""

        return value in ('big', 'little')

    @_validator
    def sign(self, value):
        """The default signedness used for e.g. the
        :func:`pwnlib.util.packing.pack` function. Defaults to ``unsigned``.

        Allowed values:

        * ``unsigned``
        * ``signed``"""

        return value in ('unsigned', 'signed')

    @_validator
    def timeout(self, value):
        """The default timeout used by e.g. :class:`pwnlib.tubes.ssh`.

        Defaults to None, meaning no timeout.

        Allowed values are any strictly positive number or None."""

        return type(value) in [types.IntType,
                               types.LongType,
                               types.FloatType] and value >= 0

    @_validator
    def word_size(self, value):
        """The default word size used for e.g. the
        :func:`pwnlib.util.packing.pack` function. Defaults to ``32``.

        Allowed values are any strictly positive number."""

        return type(value) in [types.IntType, types.LongType] and value > 0

    @_updater
    def log_level(self, value):
        """The amount of output desired from the :mod:`pwnlib.log` module.

        Allowed values are any numbers or a string.

        If a string is given, we uppercase the string and lookup it
        up in the log module.

        E.g if ``'debug'`` is specified, then the result is ``10``, as
        :data:`pwnlib.log_levels.DEBUG` is ``10``.
"""

        if type(value) in [types.IntType, types.LongType, types.NoneType]:
            return value
        elif type(value) == types.StringType:
            if hasattr(log_levels, value.upper()):
                return getattr(log_levels, value.upper())

        raise AttributeError(
            'Cannot set context-key log_level, ' +
            'as the value %r did not validate' % value
        )

    def __dir__(self):
        res = set(dir(super(ContextModule, self))) | set(properties().keys())
        if self.defaults:
            res |= set(dir(self.defaults))
        return sorted(res)


class MainModule(types.ModuleType):
    '''The module for thread-local context variables.

The purpose of this module is to store runtime configuration of pwntools, such
as the level of logging or the default architecture for shellcode.

It is implemented as a restricted dictionary, with a predefined number of
keys and with each key having restrictions of which values it will allow.

The values are available both in a thread-local version and as a global
default. You are able to read or write each version separately. If you try to
read from the thread-local version, and no value is found, then the global
default is checked.

The module :mod:`pwnlib.context` is for accessing the thread-local version,
while the global defaults are available in :mod:`pwnlib.context.defaults`.

.. note::

   Ideally, we would want to clone the thread-local context on thread creation,
   but do not know of a way to hook thread creation.

The variables in this module can be read or written directly. If you try to
write an invalid value, an exception is thrown:

.. doctest:: context_example

   >>> print context.arch
   None
   >>> context.arch = 'i386'
   >>> print context.arch
   i386
   >>> context.arch = 'mill'
   Traceback (most recent call last):
       ...
   AttributeError: Cannot set context-key arch, as the value 'mill' did not validate

For a few variables, a slight translation occur when you try to set the
variable. An example of this is :data:`pwnlib.context.log_level`:

.. doctest:: context_log_level

   >>> context.log_level = 33
   >>> print context.log_level
   33
   >>> context.log_level = 'debug'
   >>> print context.log_level
   10

In this case the translation is done by looking up the string in
:mod:`pwnlib.log`, so the result happens because :data:`pwnlib.log_levels.DEBUG`
is ``10``.

A read can never throw an exception. If there is no result in the thread-local
dictionary, the global dictionary is queried. If it has no results either,
``None`` is returned.
'''

    def __init__(self):
        super(MainModule, self).__init__(__name__)
        sys.modules[self.__name__] = self
        self.__dict__.update({
            '__all__'     : ['defaults', 'local', 'reset_local'],
            '__doc__'     : MainModule.__doc__,
            '__file__'    : __file__,
            '__package__' : __package__,
            'defaults'    : ContextModule(),
            '_ctxs'       : {},
        })
        sys.modules[self.__name__ + '.defaults'] = self.defaults
        for k, v in defaults.items():
            setattr(self.defaults, k, v)

    def __call__(self, **kwargs):
        """Convenience function, which is shorthand for setting multiple
        variables at once.

        It is a simple shorthand such that::

            context(a = b, c = d, ...)

        is equivalent to::

            context.a = b
            context.c = d
            ...

        Args:
          kwargs: Variables to be assigned in the environment.

        Examples:

          .. doctest:: context

             >>> context(arch = 'i386', os = 'linux')
             >>> print context.arch
             i386
"""

        for k, v in kwargs.items():
            setattr(self, k, v)

    def _thread_ctx(self):
        return self._ctxs.setdefault(
            threading.current_thread().ident, ContextModule(self.defaults)
        )

    def __getattr__(self, key):
        return getattr(self._thread_ctx(), key)

    def __setattr__(self, key, value):
        setattr(self._thread_ctx(), key, value)

    def local(self, **kwargs):
        '''Create a new thread-local context.

        This function creates a `context manager <https://docs.python.org/2/reference/compound_stmts.html#the-with-statement>`_,
        which will create a new environment upon entering and restore the old
        environment upon exiting.

        As a convenience, it also accepts a number of kwarg-style arguments for
        settings variables in the newly created environment.

        Args:
          kwargs: Variables to be assigned in the new environment.

        Returns:
          Context manager for managing the old and new environment.

        Examples:

          .. doctest:: context_local

             >>> print context.arch
             None
             >>> with context.local(arch = 'i386'):
             ...     print context.arch
             ...     context.arch = 'mips'
             ...     print context.arch
             i386
             mips
             >>> print context.arch
             None
'''

        return Local(kwargs)

    def reset_local(self):
        '''Completely clears the current thread-local context, thus making the
        value from :mod:`pwnlib.context.defaults` "shine through".'''
        ctx = self._thread_ctx()
        for k in dir(ctx):
            if k[0] == '_' and k[:2] != '__' and hasattr(ctx, k):
                delattr(ctx, k)

    def __dir__(self):
        res = set(dir(super(MainModule, self))) | set(dir(self._thread_ctx()))
        return sorted(res)

# prevent this scope from being GC'ed
tether = sys.modules[__name__]
context = MainModule()
