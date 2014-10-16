import sys, os, re, logging
from os.path import join, isdir, isfile, splitext, dirname, abspath
from types import ModuleType
from . import internal
from ..context import context

log = logging.getLogger(__name__)

template_dir = join(dirname(abspath(__file__)), 'templates')

def is_identifier(x):
    """
    Returns:
        ``True`` if ``x`` is a valid Python identifier;
        otherwise ``False``.
    """
    identifier = '^[a-zA-Z][a-zA-Z0-9_]*$'
    return bool(re.match(identifier, x))


#
# Lazy-initialized module for processing shellcraft mako templates.
#
# Defers most activity or searching for modules until __getattr__
# or __dir__ are invoked on the module object.
#
class lazymodule(ModuleType):

    def __init__(self, name, directory):
        """
        Initialize a directory of mako templates as a module object.

        Arguments:
            name(str): Module name
            directory(str): Full path to the directory
        """
        super(lazymodule, self).__init__(name)

        # Standard module fields
        self.__file__    = __file__
        self.__package__ = __package__
        self.__path__    = __path__

        # Internal fields
        self._dir        = directory
        self._absdir     = join(template_dir, directory)
        self._submodules = {} # 'i386'  => lazymodule('pwnlib.shellcraft.i386')
        self._shellcodes = {} # 'dupsh' => 'i386/linux/dupsh.asm'

        # Load the docstring from the '__doc__' file
        try:
            with open(join(self._absdir, "__doc__")) as fd:
                self.__doc__ = fd.read()
        except IOError:
            self.__doc__ = 'No documentation.'

        # Insert into the module list
        sys.modules[self.__name__] = self

    def __lazyinit__(self):
        """
        Performs the actual lazy initialization
        """

        for name in os.listdir(self._absdir):
            path = join(self._absdir, name)

            if isdir(path):
                mod_name = self.__name__ + '.' + name
                mod_path = join(self._dir, name)

                self._submodules[name] = lazymodule(mod_name, mod_path)

            elif isfile(path):
                funcname, ext = splitext(name)

                if not is_identifier(funcname) or ext != '.asm':
                    continue

                self._shellcodes[funcname] = name


        # Put the submodules into toplevel
        self.__dict__.update(self._submodules)

        # These are exported
        self.__all__ = sorted(self._shellcodes.keys() + self._submodules.keys())

        # Make sure this is not called again
        self.__lazyinit__ = None

    def __getattr__(self, key):
        self.__lazyinit__ and self.__lazyinit__()

        # Maybe the lazyinit added it
        try:                    super(lazymodule, self).__getattr__(key)
        except AttributeError:  pass

        # This function lazy-loads the shellcodes
        if key in self._shellcodes:
            real = internal.make_function(key, self._shellcodes[key], self._dir)
            setattr(self, key, real)
            return real

        for m in self._context_modules():
            try:
                return getattr(m, key)
            except AttributeError:
                pass

        raise AttributeError("lazymodule' object has no attribute '%s'" % key)

    def __dir__(self):
        # This function lists the available submodules, available shellcodes
        # and potentially shellcodes available in submodules that should be
        # avilable because of the context
        self.__lazyinit__ and self.__lazyinit__()

        result = list(self._submodules.keys())
        result.extend(('__file__', '__package__', '__path__',
                       '__all__',  '__name__'))
        result.extend(self.__shellcodes__())

        return result

    def _context_modules(self):
        self.__lazyinit__ and self.__lazyinit__()
        for k, m in self._submodules.items():
            yield m

    def __shellcodes__(self):
        result = self._shellcodes.keys()
        for m in self._context_modules():
            result.extend(m.__shellcodes__())
        return result

# To prevent garbage collection
tether = sys.modules[__name__]

# Create the module structure
lazymodule(__name__, '')
