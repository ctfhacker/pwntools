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
    try: word_size = int(word_size)
    except: pass

    if word_size not in valid:
        raise ValueError("word_size must be one of %r" % (valid,))
    return word_size

def ValidateArch(arch, context_dict=None):
    """ValidateArch(arch, context_dict=None) => str

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

    >>> ValidateArch('mips')
    'mips'
    >>> ValidateArch('ppc')
    'powerpc'
    >>> ValidateArch('aarch64')
    'arm'
    >>> ValidateArch('doge')
    Traceback (most recent call last):
     ...
    ValueError: arch must be one of ('alpha', 'amd64', 'arm', 'cris', 'i386', 'm68k', 'mips', 'powerpc', 'thumb')
    >>> ctx = {}
    >>> ValidateArch('powerpc64be', ctx)
    'powerpc'
    >>> ctx == {'endianness': 'big', 'word_size': 64}
    True
    >>> ValidateArch('mipsel', ctx)
    Traceback (most recent call last):
     ...
    UserWarning: endianness specified with arch ('mipsel'); endianness is already set ('little')
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

    transform = {
        'aarch': 'arm',
        'ppc':   'powerpc'
    }

    for k, v in transform.items():
        if arch.startswith(k):
            arch = arch.replace(k,v,1)

    endian    = None
    word_size = None
    arch      = arch.lower()

    if context_dict is None:
        context_dict = {}

    while arch not in valid:
        # Attempt to handle "mipsle" or "armeb", and override the default
        # if an explicit value has not been set.
        try:
            endianness = ValidateEndianness(arch[-2:])
            if 'endianness' not in context_dict:
                context_dict['endianness'] = endianness
            else:
                raise UserWarning("endianness specified with arch (%r); endianness is already set (%r)" % (arch, endianness))
            arch = arch[:-2]
            continue
        except ValueError:
            pass

        # Attempt to handle "powerpc64" or "arm64", and override the default
        # if an explicit value has not been set.
        try:
            word_size = ValidateWordSize(arch[-2:])
            if 'word_size' not in context_dict:
                context_dict['word_size'] = word_size
            else:
                raise UserWarning("word_size specified with arch (%r); word_size is already set (%r)" % (arch, word_size))
            arch = arch[:-2]
            continue
        except ValueError:
            pass

        # Raise an exception, as it's still not valid and we can't make it better
        raise ValueError('arch must be one of %r' % (valid,))

    return arch

if __name__ == "__main__":
    import doctest
    doctest.testmod()