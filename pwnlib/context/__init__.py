#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Implements context management so that nested/scoped contexts and threaded
contexts work properly and as expected.
"""
import types, sys, threading, re, collections, string, logging, collections

class _defaultdict(dict):
    """
    Dictionary which loads missing keys from another dictionary.

    This is neccesary because the ``default_factory`` method of
    :class:`collections.defaultdict` does not provide the key.

    Examples:

        >>> a = {'foo': 'bar'}
        >>> b = pwnlib.context._defaultdict(a)
        >>> b['foo']
        'bar'
        >>> 'foo' in b
        False
        >>> b['foo'] = 'baz'
        >>> b['foo']
        'baz'
        >>> del b['foo']
        >>> b['foo']
        'bar'

        >>> a = {'foo': 'bar'}
        >>> b = pwnlib.context._defaultdict(a)
        >>> b['baz'] #doctest: +ELLIPSIS
        Traceback (most recent call last):
        ...
        KeyError: 'baz'
    """
    def __init__(self, default=None):
        super(_defaultdict, self).__init__()
        if default is None:
            default = {}

        self.default = default


    def __missing__(self, key):
        return self.default[key]

class _DictStack(object):
    """
    Manages a dictionary-like object, permitting saving and restoring from
    a stack of states via :func:`push` and :func:`pop`.

    The underlying object used as ``default`` must implement ``copy``, ``clear``,
    and ``update``.

    Examples:

        >>> t = pwnlib.context._DictStack(default={})
        >>> t['key'] = 'value'
        >>> t
        {'key': 'value'}
        >>> t.push()
        >>> t
        {'key': 'value'}
        >>> t['key'] = 'value2'
        >>> t
        {'key': 'value2'}
        >>> t.pop()
        >>> t
        {'key': 'value'}
    """
    def __init__(self, default):
        self._current = _defaultdict(default)
        self.__stack  = []

    def push(self):
        self.__stack.append(self._current.copy())

    def pop(self):
        self._current.clear()
        self._current.update(self.__stack.pop())

    def copy(self):
        return self._current.copy()

    # Pass-through container emulation routines
    def __len__(self):              return self._current.__len__()
    def __delitem__(self, k):       return self._current.__delitem__(k)
    def __getitem__(self, k):       return self._current.__getitem__(k)
    def __setitem__(self, k, v):    return self._current.__setitem__(k, v)
    def __contains__(self, k):      return self._current.__contains__(k)
    def __iter__(self):             return self._current.__iter__()
    def __repr__(self):             return self._current.__repr__()
    def __eq__(self, other):        return self._current.__eq__(other)

    # Required for keyword expansion operator ** to work
    def keys(self):                 return self._current.keys()
    def values(self):               return self._current.values()
    def items():                    return self._current.items()


class _Tls_DictStack(threading.local, _DictStack):
    """
    Per-thread implementation of :class:`_DictStack`.

    Examples:

        >>> t = pwnlib.context._Tls_DictStack({})
        >>> t['key'] = 'value'
        >>> print t
        {'key': 'value'}
        >>> def p(): print t
        >>> thread = threading.Thread(target=p)
        >>> _ = (thread.start(), thread.join())
        {}
    """
    pass


def _validator(validator):

    name = validator.__name__
    doc  = validator.__doc__

    def fget(self):
        return self._tls[name]

    def fset(self, val):
        self._tls[name] = validator(self, val)

    def fdel(self):
        self._tls.pop(name,None)

    return property(fget, fset, fdel, doc)

class Thread(threading.Thread):
    """
    ContextType-aware thread.  For convenience and avoiding confusion with
    :class:`threading.Thread`, this object can be instantiated via
    :func:`pwnlib.context.thread`.

    Saves a copy of the context when instantiated (at ``__init__``)
    and updates the new thread's context before passing control
    to the user code via ``run`` or ``target=``.

    Examples:

        >>> context.reset_local()
        >>> context(arch='arm')
        ContextType(arch = 'arm')
        >>> def p():
        ...     print context
        ...     context.arch = 'mips'
        ...     print context
        >>> # Note that a normal Thread starts with a clean context
        >>> t = threading.Thread(target=p)
        >>> _=(t.start(), t.join())
        ContextType()
        ContextType(arch = 'mips')
        >>> # Note that the main Thread's context is unchanged
        >>> context
        ContextType(arch = 'arm')
        >>> # Note that a context-aware Thread receives a copy of the context
        >>> t = Thread(target=p)
        >>> _=(t.start(), t.join())
        ContextType(arch = 'arm')
        ContextType(arch = 'mips')
        >>> context
        ContextType()

    Implementation Details:

        This class implemented by hooking the private function
        :func:`threading.Thread._Thread_bootstrap`, which is called before
        passing control to :func:`threading.Thread.run`.

        This could be done by overriding ``run`` itself, but we would have to
        ensure that all uses of the class would only ever use the keyword
        ``target=`` for ``__init__``, or that all subclasses invoke
        ``super(Subclass.self).set_up_context()`` or similar.
    """
    def __init__(self, *args, **kwargs):
        super(Thread, self).__init__(*args, **kwargs)
        self.old = context.copy()

    def __bootstrap(self):
        """
        Implementation Details:
            This only works because the class is named ``Thread``.
            If its name is changed, we have to implement this hook
            differently.
        """
        context.update(**self.old)
        super(Thread, self).__bootstrap()

def _longest(d):
    """
    Returns an OrderedDict with the contents of the input dictionary ``d``
    sorted by the length of the keys, in descending order.

    This is useful for performing substring matching via ``str.startswith``,
    as it ensures the most complete match will be found.

    >>> data = {'a': 1, 'bb': 2, 'ccc': 3}
    >>> _longest(data) == data
    True
    >>> for i in _longest(data): print i
    ccc
    bb
    a
    """
    return collections.OrderedDict((k,d[k]) for k in sorted(d, key=len, reverse=True))

def TlsProperty(object):
    def __get__(self, obj, objtype=None):
        return obj._tls

class ContextType(object):
    r"""
    Class for specifying information about the target machine.
    Intended for use as a pseudo-singleton through the global
    variable ``pwnlib.context.context``, available via
    ``from pwn import *`` as ``context``.

    The context is usually specified at the top of the Python file for clarity. ::

        #!/usr/bin/env python
        context(arch='i386', os='linux')

    Currently supported properties and their defaults are listed below.
    The defaults are inherited from :data:`pwnlib.context.ContextType.defaults`.

    Additionally, the context is thread-aware when using
    :class:`pwnlib.context.Thread` instead of :class:`threading.Thread`
    (all internal ``pwntools`` threads use the former).

    The context is also scope-aware by using the ``with`` keyword.

    Examples:

        >>> context
        ContextType()
        >>> context.update(os='linux')
        ...
        >>> context.os == 'linux'
        True
        >>> context.arch = 'arm'
        >>> context.copy() == {'arch': 'arm', 'os': 'linux'}
        True
        >>> context.endian
        'little'
        >>> context.bits
        32
        >>> def nop():
        ...   print pwnlib.asmasm('nop').encode('hex')
        >>> nop()
        00f020e3
        >>> with context.local(arch = 'i386'):
        ...   nop()
        90
        >>> with context.local(arch = 'mips'):
        ...     pwnthread = context.thread(target=nop)
        ...     thread = threading.Thread(target=nop)
        >>> # Normal thread uses the default value for arch, 'i386'
        >>> _=(thread.start(), thread.join())
        90
        >>> # Pwnthread uses the correct context from creation-time
        >>> _=(pwnthread.start(), pwnthread.join())
        00000000
        >>> nop()
        00f020e3
    """

    #
    # Use of 'slots' is a heavy-handed way to prevent accidents
    # like 'context.architecture=' instead of 'context.arch='.
    #
    # Setting any properties on a ContextType object will throw an
    # exception.
    #
    __slots__ = '_tls',

    #: Default values for :class:`pwnlib.context.ContextType`
    defaults = {
        'bits': 32,
        'os': 'linux',
        'arch': 'i386',
        'endian': 'little',
        'signed': False,
        'timeout': 1,
        'log_level': logging.INFO
    }

    #: Valid values for :meth:`pwnlib.context.ContextType.os`
    oses = sorted(('linux','freebsd','windows'))

    big_32    = {'endian': 'big', 'bits': 32}
    big_64    = {'endian': 'big', 'bits': 64}
    little_16 = {'endian': 'little', 'bits': 16}
    little_32 = {'endian': 'little', 'bits': 32}
    little_64 = {'endian': 'little', 'bits': 64}

    #: Keys are valid values for :meth:`pwnlib.context.ContextType.arch`.
    #
    #: Values are defaults which are set when
    #: :attr:`pwnlib.context.ContextType.arch` is set
    architectures = _longest({
        'aarch64':   little_64,
        'alpha':     little_64,
        'amd64':     little_64,
        'arm':       little_32,
        'cris':      little_32,
        'i386':      little_64,
        'm68k':      big_32,
        'mips':      little_32,
        'mips64':    little_64,
        'msp430':    little_16,
        'powerpc':   big_32,
        'powerpc64': big_64,
        's390':      big_32,
        'thumb':     little_32,
    })

    #: Valid values for :attr:`endian`
    endiannesses = _longest({
        'be':     'big',
        'eb':     'big',
        'big':    'big',
        'le':     'little',
        'el':     'little',
        'little': 'little'
    })

    #: Valid string values for :attr:`signed`
    signednesses = {
        'unsigned': False,
        'no':       False,
        'yes':      True,
        'signed':   True
    }

    def __init__(self, **kwargs):
        """
        Initialize the ContextType structure.

        All keyword arguments are passed to :func:`update`.
        """
        self._tls = _Tls_DictStack(_defaultdict(ContextType.defaults))
        self.update(**kwargs)


    def copy(self):
        """
        Returns a copy of the current context as a dictionary.

        Examples:

            >>> context.reset_local()
            >>> context.arch = 'i386'
            >>> context.os   = 'linux'
            >>> context.copy() == {'arch': 'i386', 'os': 'linux'}
            True
        """
        return self._tls.copy()

    def update(self, *args, **kwargs):
        """
        Convenience function, which is shorthand for setting multiple
        variables at once.

        It is a simple shorthand such that::

            context.update(os = 'linux', arch = 'arm', ...)

        is equivalent to::

            context.os   = 'linux'
            context.arch = 'arm'
            ...

        The following syntax is also valid::

            context.update({'os': 'linux', 'arch': 'arm'})

        Args:
          kwargs: Variables to be assigned in the environment.

        Examples:

            >>> context.arch.reset_local()
            >>> context(arch = 'i386', os = 'linux')
            ...
            >>> context.arch, context.os
            ('i386', 'linux')
        """
        for arg in args:
            self.update(**arg)

        for k,v in kwargs.items():
            setattr(self,k,v)

        return self

    def __repr__(self):
        v = sorted("%s = %r" % (k,v) for k,v in self._tls._current.items())
        return '%s(%s)' % (self.__class__.__name__, ', '.join(v))

    def local(self, **kwargs):
        """
        Create a context manager for use with the ``with`` statement.

        For more information, see the example below or PEP 343.

        Args:
          kwargs: Variables to be assigned in the new environment.

        Returns:
          ContextType manager for managing the old and new environment.

        Examples:
            >>> context
            ContextType()
            >>> with context.local(arch = 'mips'):
            ...     print context
            ...     context.arch = 'arm'
            ...     print context
            ContextType(arch = 'mips')
            ContextType(arch = 'arm')
            >>> print context
            ContextType()
        """
        class LocalContext(object):
            def __enter__(a):
                self._tls.push()
                self.update(**{k:v for k,v in kwargs.items() if v is not None})
                return self

            def __exit__(a, *b, **c):
                self._tls.pop()

        return LocalContext()

    def reset_local(self):
        """
        Clears the contents innermost scoped context on the context stack.

        Examples:

            >>> # Default value
            >>> print context.os
            i386
            >>> # Inside of a scope, use reset_local
            >>> context.os = 'arm'
            >>> with context.local():
            ...     print context.os
            ...     context.reset_local()
            ...     print context.os
            arm
            i386
            >>> # Outer scope is unaffected
            >>> print context.os
            arm
            >>> # It can also be used in the global scope
            >>> context.reset_local()
            >>> print context.os
            i386
        """
        self._tls._current.clear()

    def thread(self, *args, **kwargs):
        """
        Instantiates a context-aware thread, which inherit its context
        when it is instantiated.

        Threads created in any other manner will have a clean (default)
        context.

        Regardless of the mechanism used to create any thread, the context
        is de-coupled from the parent thread, so changes do not cascade
        to child or parent.

        Arguments:

            The same arguments are used as :class:`threading.Thread`.

        Examples:

            See the documentation for :class:`pwnlib.context.Thread` for
            examples.
        """
        return Thread(*args, **kwargs)

    @property
    def arch(self):
        """
        Target machine architecture.

        Allowed values are listed in :attr:`pwnlib.context.ContextType.architectures`.

        .. _side-effects:
        Side Effects:

            Depending on the architecture specified, the default values for
            the following default values for context properties may be updated:

            - :attr:`bits`
            - :attr:`endian`

            Note that these changes only affect the **default** context values.
            They will not override user-specified values.

        Raises:
            ValueError: An invalid architecture was specified

        Examples:
            >>> context.reset_local()
            >>> context.arch == 'i386' # Default architecture
            True

            >>> context.arch = 'mips'
            >>> context.arch == 'mips'
            True

            >>> context.arch = 'doge' #doctest: +ELLIPSIS
            Traceback (most recent call last):
             ...
            ValueError: arch must be one of ['alpha', ..., 'thumb']

            >>> context.arch = 'ppc'
            >>> context.arch == 'powerpc' # Aliased architecture
            True

            >>> context.reset_local()
            >>> context.bits == 32 # Default value
            True
            >>> context.arch = 'amd64'
            >>> context.bits == 64 # New default value
            True

            Note that expressly setting :attr:`bits` means that we use
            that value instead of the default

            >>> context.reset_local()
            >>> context.bits = 32
            >>> context.arch = 'aarch64'
            >>> context.bits == 32
            True

            Setting the architecture can override the defaults for
            both :attr:`endian` and :attr:`bits`

            >>> context.reset_local()
            >>> context.arch = 'powerpc64'
            >>> context.endian == 'big'
            True
            >>> context.bits == 64
            True
            >>> context.arch == 'powerpc'
            True
        """
        return self._tls['arch']


    @arch.setter
    def arch(self, arch):
        # Lowercase, remove everything non-alphanumeric
        arch = arch.lower()
        arch = arch.replace(string.punctuation, '')

        # Attempt to perform convenience and legacy compatibility
        # transformations.
        transform = {'x86':'i386', 'ppc': 'powerpc'}
        for k, v in transform.items():
            if arch.startswith(k):
                arch = arch.replace(k,v,1)

        try:
            self.defaults.update(ContextType.architectures[arch])
        except KeyError:
            raise ValueError('arch must be one of %r' % sorted(ContextType.architectures))
        else:
            self._tls['arch'] = arch

    @property
    def bits(self):
        """
        Word size of the target machine, in bits (i.e. the size of general purpose registers).

        The default value is ``32``, but changes according to :attr:`arch`.

        Examples:
            >>> context.reset_local()
            >>> context.bits == 32
            True
            >>> context.bits = 64
            >>> context.bits == 64
            True
            >>> context.bits = -1 #doctest: +ELLIPSIS
            Traceback (most recent call last):
            ...
            ValueError: bits must be >= 0 (-1)
        """
        return self._tls['bits']

    @bits.setter
    def bits(self, bits):
        bits = int(bits)

        if bits <= 0:
            raise ValueError("bits must be >= 0 (%r)" % bits)

        self._tls['bits'] = bits

    @property
    def bytes(self):
        """
        Word size of the target machine, in bytes (i.e. the size of general purpose registers).

        This is a convenience wrapper around ``bits / 8``.

        Examples:
            >>> context.bytes = 1
            >>> context.bits == 8
            True

            >>> context.bytes = 0 #doctest: +ELLIPSIS
            Traceback (most recent call last):
            ...
            ValueError: bits must be >= 0 (0)
        """
        return self.bits / 8

    @bytes.setter
    def bytes(self, value):
        self.bits = 8*value

    @property
    def endian(self):
        """
        Endianness of the target machine.

        The default value is ``'little'``, but changes according to :attr:`arch`.

        Raises:
            ValueError: An invalid endianness was provided

        Examples:
            >>> context.reset_local()
            >>> context.endian == 'little'
            True

            >>> context.endian = 'big'
            >>> context.endian
            'big'

            >>> context.endian = 'be'
            >>> context.endian == 'big'
            True

            >>> context.endian = 'foobar' #doctest: +ELLIPSIS
            Traceback (most recent call last):
             ...
            ValueError: endian must be one of ['be', 'big', 'eb', 'el', 'le', 'little']
        """
        return self._tls['endian']

    @endian.setter
    def endian(self, endian):
        endian = endianness.lower()

        if endian not in ContextType.endiannesses:
            raise ValueError("endian must be one of %r" % sorted(ContextType.endiannesses))

        self._tls['endian'] = ContextType.endiannesses[endian]


    @property
    def keep_line_ends(self):
        r"""
        Determines whether, by default, :meth:`pwnlib.tubes.tube.tube.recvline`
        and related routines will strip newlines.

        Default value is ``True``

        Examples:

            >>> context.keep_line_ends
            True
            >>> t = pwnlibe.tubes.tube.tube()
            >>> t.recv_raw = lambda: 'Hello\nWorld\n'
            >>> t.recvline()
            'Hello\n'
            >>> contet.keep_line_ends = False
            >>> t.recvline()
            'World'
        """

        return self._tls['keep_line_ends']

    @keep_line_ends.setter
    def keep_line_ends(self, value):
        self._tls['keep_line_ends'] = bool(value)

    @property
    def os(self):
        """
        Operating system of the target machine.

        The default value is ``linux``.

        Allowed values are listed in :attr:`pwnlib.context.ContextType.oses`.

        Examples:
            >>> context.os = 'linux'
            >>> context.os = 'foobar' #doctest: +ELLIPSIS
            Traceback (most recent call last):
            ...
            ValueError: os must be one of ['freebsd', 'linux', 'windows']
        """
        return self._tls['os']

    @os.setter
    def os(self, os):
        os = os.lower()

        if os not in ContextType.oses:
            raise ValueError("os must be one of %r" % sorted(ContextType.oses))

        self._tls['os'] = os

    @property
    def timeout(self):
        """
        Default amount of time to wait for a blocking operation before it times out,
        specified in seconds.

        The default value is ``1``.

        Any floating point value is accepted, as well as the special
        string ``'inf'`` which implies that a timeout can never occur.


        Examples:
            >>> context.timeout == 1
            True
            >>> context.timeout = 'inf'
            >>> context.timeout > 2**256
            True
            >>> context.timeout - 30
            inf
        """
        return self._tls['timeout']

    @timeout.setter
    def timeout(self, value):
        value = float(value)

        if value < 0:
            raise ValueError("timeout must not be negative (%r)" % value)

        self._tls['timeout'] = value


    @property
    def log_level(self):
        """
        Sets the verbosity of ``pwntools`` logging mechanism.

        Valid values are specified by the standard Python ``logging`` module.

        Default value is set to ``INFO``.

        Examples:
            >>> context.log_level == logging.INFO
            True
            >>> context.log_level = 'error'
            >>> context.log_level == logging.ERROR
            True
            >>> context.log_level = 10
            >>> context.log_level = 'foobar' #doctest: +ELLIPSIS
            Traceback (most recent call last):
            ...
            ValueError: log_level must be an integer or one of ['CRITICAL', 'DEBUG', 'ERROR', 'INFO', 'NOTSET', 'WARN', 'WARNING']
        """
        return self._tls['log_level']

    @log_level.setter
    def log_level(self, value):
        # If it can be converted into an int, success
        try:                    self._tls['log_level'] = int(value)
        except ValueError:      pass
        else:                   return

        # If it is defined in the logging module, success
        try:                    self._tls['log_level'] = getattr(logging, value.upper())
        except AttributeError:  pass
        else:                   return

        # Otherwise, fail
        level_names = filter(lambda x: isinstance(x,str), logging._levelNames)
        permitted = sorted(level_names)
        raise ValueError('log_level must be an integer or one of %r' % permitted)


    @property
    def signed(self):
        """
        Signed-ness for packing operation when it's not explicitly set.

        Can be set to any non-string truthy value, or the specific string
        values ``'signed'`` or ``'unsigned'`` which are converted into
        ``True`` and ``False`` correspondingly.

        Examples:
            >>> context.signed
            False
            >>> context.signed = 1
            >>> context.signed
            True
            >>> context.signed = 'signed'
            >>> context.signed
            True
            >>> context.signed = 'unsigned'
            >>> context.signed
            False
            >>> context.signed = 'foobar' #doctest: +ELLIPSIS
            Traceback (most recent call last):
            ...
            ValueError: signed must be one of ['no', 'signed', 'unsigned', 'yes'] or a non-string truthy value
        """
        return self._tls['signed']

    @signed.setter
    def signed(self, signed):
        try:             signed = ContextType.signednesses[signed]
        except KeyError: pass

        if isinstance(signed, str):
            raise ValueError('signed must be one of %r or a non-string truthy value' % sorted(ContextType.signednesses))

        self._tls['signed'] = bool(signed)


    @property
    def newline(self):
        r"""
        Defines the newline character, as interpreted by objects from
        :mod:`pwntools.tubes`.

        Default value is ``'\n'``

        Examples:

            >>> context.newline
            '\n'
            >>> t = pwnlib.tubes.tube.tube()
            >>> t.recv_raw = lambda: 'Hello\r\nWorld\r\n'
            >>> t.recvlines(2)
            ['Hello\r', 'World\r']
            >>> context.newline = '\r\n'
            >>> t.recvlines(2)
            ['Hello', 'World']
        """

        return self._tls['newline']
    @newline.setter
    def newline(self, value):
        self._tls['newline'] = value


    @property
    def foo(self):
        return self._foo
    @foo.setter
    def foo(self, value):
        self._foo = value




    #*************************************************************************
    #                           DEPRECATED FIELDS
    #*************************************************************************
    #
    # These fields are deprecated, but support is ensured for backward
    # compatibility.
    #
    #*************************************************************************

    def __call__(self, **kwargs):
        """
        Alias for :meth:`pwnlib.context.ContextType.update`
        """
        return self.update(**kwargs)

    @property
    def word_size(self):
        """
        Alias for :attr:`bits`
        """
        return self.bits

    @word_size.setter
    def word_size(self, value):
        self.bits = value

    @property
    def signedness(self):
        """
        Alias for :attr:`signed`
        """
        return self.signed

    @signedness.setter
    def signedness(self, value):
        self.signed = value

    @property
    def sign(self):
        """
        Alias for :attr:`signed`
        """
        return self.signed

    @sign.setter
    def sign(self, value):
        self.signed = value


    @property
    def endianness(self):
        """
        Legacy alias for :attr:`endian`.

        Examples:
            >>> context.endian == context.endianness
            True
        """
        return self.endian
    @endianness.setter
    def endianness(self, value):
        self.endian = value

context = ContextType()
