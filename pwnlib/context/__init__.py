#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Implements context management so that nested/scoped contexts and threaded
contexts work properly and as expected.
"""
import types, sys, threading, re, collections, string, logging

class _defaultdict2(collections.defaultdict):
    """
    Dictionary which loads missing keys from another dictionary.

    This is neccesary because the ``default_factory`` method of
    :class:`collections.defaultdict` does not provide the key.

        Examples:

            .. doctest::

                >>> a = {'foo': 'bar'}
                >>> b = _defaultdict2(a)
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
                >>> b = _defaultdict2(a)
                >>> b['baz']
                Traceback (most recent call last):
                ...
                KeyError: 'baz'
    """
    def __init__(self, default=None):
        if default is None:
            default = {}

        self.default = default

        super(_defaultdict2, self).__init__(None)
    def __missing__(self, key):
        return self.default[key]
    def __repr__(self):
        return dict.__repr__(self)
    def __str__(self):
        return dict.__str__(self)
    def copy(self):
        copy = _defaultdict2(self.default)
        copy.update(self)
        return copy

class _DictStack(object):
    """
    Manages a dictionary-like object, permitting saving and restoring from
    a stack of states via :func:`push` and :func:`pop`.

    The underlying object used as ``default`` must implement ``copy``, ``clear``,
    and ``update``.

        Examples:

            .. doctest::

                >>> t = _DictStack(default={})
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
        self._current = default
        self.__stack  = []

    def push(self):
        self.__stack.append(self._current.copy())

    def pop(self):
        self._current.clear()
        self._current.update(self.__stack.pop())

    def copy(self):
        return self.__class__(self._current.copy())

    # Pass-through container emulation routines
    def __len__(self):              return self._current.__len__()
    def __delitem__(self, k):       return self._current.__delitem__(k)
    def __getitem__(self, k):       return self._current.__getitem__(k)
    def __setitem__(self, k, v):    return self._current.__setitem__(k, v)
    def __contains__(self, k):      return self._current.__contains__(k)
    def __iter__(self):             return self._current.__iter__()
    def __repr__(self):             return self._current.__repr__()

    # Required for keyword expansion operator ** to work
    def keys(self):                 return self._current.keys()
    def values(self):               return self._current.values()
    def items():                    return self._current.items()


class _Tls_DictStack(threading.local, _DictStack):
    """
    Per-thread implementation of :class:`_DictStack`.

        Examples:

            .. doctest::

                >>> t = _Tls_DictStack()
                >>> t['key'] = 'value'
                >>> t
                {'key': 'value'}
                >>> def p(): print t
                >>> threading.Thread(target=p).start()
                {}
    """
    pass


class Thread(threading.Thread):
    """
    Context-aware thread.  For convenience and avoiding confusion with
    :class:`threading.Thread`, this object can be instantiated via
    :func:`pwnlib.context.thread`.

    Saves a copy of the context when instantiated (at ``__init__``)
    and updates the new thread's context before passing control
    to the user code via ``run`` or ``target=``.

    Examples:

        .. doctest::

            >>> context
            Context()
            >>> context(arch='arm')
            Context(arch = 'arm')
            >>> def p():
            ...     print context
            ...     context.arch = 'mips'
            ...     print context
            ...
            >>> t = threading.Thread(target=p)
            >>> _=(t.start(), t.join())
            Context()
            Context(arch = 'mips')
            >>> context
            Context(arch = 'arm')
            >>> t = pwnlib.context.Thread(target=p)
            >>> _=(t.start(), t.join())
            Context(arch = 'arm')
            Context(arch = 'mips')
            >>> context
            Context()

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


class Context(object):
    r"""
    Class for specifying information about the target machine.
    Intended for use as a pseudo-singleton through the global
    variable :data:`pwnlib.context.context`, available via
    ``from pwn import *`` as ``context``.

    Many classes/functions **require** that information such as the target
    OS or architecture be specified in the global ``context`` structure.

    Some routines will allow specifying a different architecture as arguments,
    but use the ``context``-provided values as defaults.

    The context is usually specified at the top of the Python file for clarity.

    .. highlight::

        #!/usr/bin/env python
        context(arch='i386', os='linux')

    Currently supported properties and their defaults are listed below.
    The defaults are inherited from :attr:`defaults`.

    Additionally, the context is thread-aware when using
    :class:`pwnlib.context.Thread` instead of :class:`threading.Thread`
    (all internal ``pwntools`` threads use the former).

    The context is also scope-aware by using the ``with`` keyword.

    Attributes:

        arch(str):      Target CPU architecture
        bits(int):      Target CPU register/word size, in bits
        bytes(int):     Target CPU register/word size, in bytes
        endian(str):    Target CPU endian-ness
        log_level(int): Logging verbosity for :mod:`pwnlib.log`
        os(str):        Target Operating System
        signed(bool):   Signed-ness for packing operations in :mod:`pwnlib.util.packing`

    Examples:

        .. doctest::

            >>> from pwn import *
            >>> context
            Context()
            >>> context.update(os='linux')
            >>> context
            Context(os = 'linux')
            >>> context(arch = 'arm')
            Context(os = 'linux', arch = 'arm')
            >>> def nop():
            ...   print asm('nop').encode('hex')
            ...
            >>> nop()
            00f020e3
            >>> with context.local(arch = 'mips'):
            ...   nop()
            00842020
            >>> with context.local(arch = 'x86'):
            ...     pwnthread = context.Thread(target=nop)
            ...     thread = threading.Thread(target=nop)
            ...
            >>> _=(thread.start(), thread.join())
            00f020e3
            >>> _=(pwnthread.start(), pwnthread.join())
            90
            >>> nop()
            00f020e3
    """

    #
    # Use of 'slots' is a heavy-handed way to prevent accidents
    # like 'context.architecture=' instead of 'context.arch='.
    #
    # Setting any properties on a Context object will throw an
    # exception.
    #
    __slots__ = '_tls',

    #: Valid values for :class:`pwnlib.context.Context`
    defaults = {
        'os': 'linux',
        'arch': 'x86',
        'endian': 'little',
        'timeout': 1,
        'log_level': logging.INFO
    }

    #: Valid values for :attr:`pwnlib.context.Context.os`
    oses = sorted(('linux','freebsd','windows'))

    #: Valid values for :attr:`pwnlib.context.Context.arch`
    architectures = sorted(('alpha',
                            'arm',
                            'cris',
                            'x86',
                            'm68k',
                            'mips',
                            'powerpc',
                            'thumb'))

    #: Valid values for :attr:`pwnlib.context.Context.endian`
    endiannesses = {
        'be': 'big',
        'eb': 'big',
        'big': 'big',
        'le': 'little',
        'el': 'little',
        'little': 'little'
    }

    #: Value values for :attr:`pwnlib.context.Context.signed`
    signednesses = {
        'unsigned': 0,
        'no':       0,
        'yes':      1,
        'signed':   1
    }


    def __init__(self, **kwargs):
        """
        Initialize the Context structure.

        All keyword arguments are passed to :func:`update`.
        """
        self._tls = _Tls_DictStack(_defaultdict2(Context.defaults))
        self.update(**kwargs)


    def copy(self):
        """
        Returns a copy of the current context as a dictionary.

        Examples:

            .. doctest::

                >>> context(arch = 'x86', os = 'linux')
                >>> context.copy() == {'arch': 'x86', 'os': 'linux'}
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

            .. doctest::

                >>> context(arch = 'x86', os = 'linux')
                >>> context.arch, context.os
                'x86', 'linux'
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
          Context manager for managing the old and new environment.

        Examples:

            .. doctest::

                >>> context
                Context()
                >>> with context.local(arch = 'mips'):
                ...     print context
                ...     context.arch = 'arm'
                ...     print context
                Context(arch = 'mips')
                Context(arch = 'arm')
                >>> print context
                Context()
        """
        class LocalContext(object):
            def __enter__(a):
                self._tls.push()
                self.update(**{k:v for k,v in kwargs.items() if v is not None})
                return self

            def __exit__(a, *b, **c):
                self._tls.pop()

        return LocalContext()


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
        Variable for the current architecture. This is useful e.g. to make
        :mod:`pwnlib.shellcraft` easier to use.

        Allowed values are enumerated in :data:`pwnlib.context.arch.valid`

        Setting this may also update :data:`pwnlib.context.word_size`
        and :data:`pwnlib.context.endianness` by specifying an architecture
        suffix in the form of ``mipsel64`` (for 64-bit little-endian
        MIPS).

        Finally, some convenience transformations may be made.
        For example, specifying 'ppc' will be tranlsated to 'powerpc'.

        Raises:
            ValueError: An invalid architecture was specified

        Examples:

            .. doctest::

                >>> context.arch == 'x86'
                True

                >>> context.arch = 'mips'
                >>> context.arch == 'mips'
                True

                >>> context.arch = 'doge'
                Traceback (most recent call last):
                 ...
                ValueError: arch must be one of ('alpha', 'arm', 'cris', 'x86', 'm68k', 'mips', 'powerpc', 'thumb')

                >>> context.arch = 'ppc'
                >>> context.arch == 'powerpc'
                True

                >>> context.bits != 64
                True
                >>> context.arch = 'aarch64'
                >>> context.bits == 64
                True

                >>> context.arch = 'powerpc32be'
                >>> context.endianness == 'big'
                True
                >>> context.bits == 32
                True
                >>> context.arch == powerpc
                True

                >>> context.arch = 'mips-64-little'
                >>> context.arch == 'mips'
                True
                >>> context.bits == 64
                True
                >>> context.endianness == 'little'
                True
        """
        return self._tls['arch']


    @arch.setter
    def arch(self, arch):
        transform = {
            'aarch': 'arm',
            'ppc':   'powerpc',
            'i386':  'x86',
            'amd64': 'x86_64' # mildly hacky
        }

        # Lowercase, remove everything non-alphanumeric
        arch = arch.lower()
        arch = arch.replace(string.punctuation, '')

        # Attempt to perform convenience and legacy compatibility
        # transformations.
        for k, v in transform.items():
            if arch.startswith(k):
                arch = arch.replace(k,v,1)


        # Attempt to match on the leading architecture name
        # Everything else is stored in 'tail'
        tail = ''

        for a in Context.architectures:
            if arch.startswith(a):
                self._tls['arch'] = a
                tail              = arch[len(a):]
                break
        else:
            raise ValueError('arch must be one of %r' % (architectures,))


        # Attempt to figure out whatever is left over.
        # Regex makes use of the fact that word_size must be digits,
        # and the endianness must be ascii.
        expr = r'([0-9]+|[a-z]+)'
        hits = re.findall(expr, tail)

        for hit in hits:
            if hit.isdigit(): self.bits       = hit
            if hit.isalpha(): self.endianness = hit


    @property
    def endianness(self):
        """
        Endianness of the target machine.

        The default value is 'little'.

        Raises:
            ValueError: An invalid endianness was provided

        Examples:

            .. doctest::

                >>> context.endianness == 'little'
                True

                >>> context.endianness = 'big'
                >>> context.endianness
                'big'

                >>> context.endianness = 'be'
                >>> context.endianness == 'big'
                True

                >>> context.endianness = 'foobar'
                Traceback (most recent call last):
                 ...
                ValueError: endianness must be one of ['be', 'big', 'eb', 'el', 'le', 'little']
        """
        return self._tls['endian']

    @endianness.setter
    def endianness(self, endianness):
        endianness = endianness.lower()

        if endianness not in Context.endiannesses:
            raise ValueError("endianness must be one of %r" % sorted(Context.endiannesses))

        self._tls['endian'] = Context.endiannesses[endianness]

    @property
    def endian(self):
        """
        Alias for ``endianness``.

        Examples:

            .. doctest::

                >>> context.endian == context.endianness
                True
        """
        return self.endianness
    @endian.setter
    def endian(self, value):
        self.endianness = value

    @property
    def os(self):
        """
        Operating system of the target machine.

        The default value is ``linux``.

        Allowed values are listed in :attr:`oses`.

        Examples:

            .. doctest::

                >>> context.os = 'linux'
                >>> context.os = 'foobar'
                Traceback (most recent call last):
                ...
                ValueError: os must be one of ('freebsd', 'linux', 'windows')
        """
        return self._tls['os']

    @os.setter
    def os(self, os):
        os = os.lower()

        if os not in Context.oses:
            raise ValueError("os must be one of %r" % sorted(Context.oses))

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

            .. doctest::

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
    def bits(self):
        """
        Word size of the target machine, in bits (i.e. the size of general purpose registers).

        The default value is ``32``.

        Examples:

            .. doctest::

                >>> context.bits == 32
                True
                >>> context.bits = 64
                >>> context.bits == 64
                True
                >>> context.bits = -1
                Traceback (most recent call last):
                ...
                ValueError: "bits must be positive (-1)"
        """
        return self._tls['bits']

    @bits.setter
    def bits(self, bits):
        bits = int(bits)

        if bits <= 0:
            raise ValueError("bits must be positive (%r)" % bits)

        self._tls['bits'] = bits

    @property
    def bytes(self):
        """
        Word size of the target machine, in bytes (i.e. the size of general purpose registers).

        This is a convenience wrapper around ``bits / 8``.

        Examples:

            .. doctest::

                >>> context.bytes = 1
                >>> context.bits == 8
                True

                >>> context.bytes = 0
                Traceback (most recent call last):
                ...
                ValueError: "bits must be positive (0)"
        """
        return self.bits / 8

    @bytes.setter
    def bytes(self, value):
        self.bits = 8*value


    @property
    def log_level(self):
        """
        Sets the verbosity of ``pwntools`` logging mechanism.

        Valid values are specified by the standard Python ``logging`` module.

        Default value is set to ``INFO``.

        Examples:

            .. doctest::

                >>> context.log_level == logging.INFO
                True

                >>> context.log_level = 'error'
                >>> context.log_level == logging.ERROR
                True

                >>> context.log_level = 10

                >>> context.log_level = 'foobar'
                Traceback (most recent call last):
                ...
                ValueError: log_level must be an integer or one of ['DEBUG', 'ERROR', 'INFO', 'SILENT']
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

            .. doctest::

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

                >>> context.signed = 'foobar'
                Traceback (most recent call last):
                ...
                ValueError: signed must be one of ['no', 'signed', 'unsigned', 'yes'] or a non-string truthy value
        """
        return self._tls['signed']

    @signed.setter
    def signed(self, signed):
        try:             signed = Context.signednesses[signed]
        except KeyError: pass

        if isinstance(object, str):
            raise ValueError('signed must be one of %r or a non-string truthy value' % sorted(Context.signednesses))

        self._tls['signed'] = bool(signed)


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
        .. deprecated::
            Legacy compatibility wrapper for :func:`update`.
            Use that instead.
        """
        return self.update(**kwargs)

    @property
    def word_size(self):
        """
        .. deprecated::
            Legacy support.  Use :attr:`bits`.
        """
        return self.bits

    @word_size.setter
    def word_size(self, value):
        self.bits = value

    @property
    def signedness(self):
        """
        .. deprecated::
            Legacy support.  Use :attr:`signed` instead.
        """
        return self.signed

    @signedness.setter
    def signedness(self, value):
        self.signed = value

    @property
    def sign(self):
        """
        .. deprecated::
            Legacy support.  Use :attr:`signed` instead.
        """
        return self.signed

    @sign.setter
    def sign(self, value):
        self.signed = value



context = Context()
