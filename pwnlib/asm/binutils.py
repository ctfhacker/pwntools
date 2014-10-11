import tempfile, subprocess, shutil, tempfile, errno
from os import path
from .log     import *
from .context import import context

__all__ = ['asm', 'cpp', 'disasm']

_basedir = path.split(__file__)[0]
_bindir  = path.join(_basedir, 'data', 'binutils')
_incdir  = path.join(_basedir, 'data', 'includes')

i386    = r'i386.*'
x86_64  = r'x86_64.*'
aarch64 = r'arm64'
ppc     = r'powerpc32'
ppc64   = r'powerpc64'
mips    = r'mips.*'

def binutils_prefix(arch=None, word_size=None):
    """binutils_prefix(arch, word_size=None) -> str

    Retrieves the binutils prefix for the specified architecture.

    Arguments:
        arch(str): Name of the architecture, e.g. 'arm'.
            Defaults to using 'context.arch'
        word_size(str): Word size on the specified architecture.
            Defaults to using 'context.word_size'

    Returns:
        String containing the prefix for the installed system
        binutils for the specified architecture.

    >>> binutils_prefix('arm')
    'arm-linux-gnueabihf-'
    >>> binutils_prefix('arm', 64)
    'aarch64-linux-gnu-'
    """

    arch      = arch      or context.arch
    word_size = word_size or context.word_size

    matchers = {
        r'i386.*': 'x86_64-linux-gnu-'
    }

def as(arch=None, word_size=None):


def _binutils_prefix(arch):
    """_binutils_prefix(arch) -> str

    Returns a tuple containing the prefix used for GNU binutils
    for the given architecture, as well as flags that should be
    passed to the utilities.
    """

def _assembler(arch):
    E = {
        'big':    '-EB',
        'little': '-EL'
    }[context.endianness]

    assemblers = {
        'i386'   : ['x86_64-linux-gnu-as', '--32'],
        'x32'    : ['x86_64-linux-gnu-as', '--x32'],
        'amd64'  : ['x86_64-linux-gnu-as', '--64'],
        'thumb'  : ['arm-linux-gnueabi-as', '-thumb', E],
        'arm'    : ['arm-linux-gnueabi-as', E],
        'aarch64': ['aarch64-linux-gnu-as', E],
        'mips'   : ['mips-linux-gnu-as', E],
        'powerpc': ['powerpc-linux-gnu-as', '-m%s' % context.endianness]
    }

    return assemblers[arch]


def _objcopy(arch):
    if arch in ['i386', 'amd64']:
        return 'objcopy'
    else:
        return path.join(_bindir, 'objcopy')


def _objdump(arch):
    if arch in ['i386', 'amd64']:
        return ['objdump', '-Mintel']
    else:
        return [path.join(_bindir, 'objdump')]


def _include_header(arch, os):
    if os == 'freebsd':
        return '#include <freebsd.h>\n'
    elif os == 'linux' and arch:
        return '#include <linux/%s.h>\n' % arch
    else:
        return ''


def _arch_header(arch):
    prefix  = ['.section .shellcode,"ax"']
    headers = {
        'i386'  : ['.intel_syntax']
        'amd64' : ['.intel_syntax'],
        'arm'   : ['.syntax unified',
                   '.arch armv7-a',
                   '.arm'],
        'thumb' : ['.syntax unified',
                   '.arch armv7-a',
                   '.thumb'],
        'mips'  : ['.set mips2',
                   '.set noreorder'],
    }

    if arch in headers:
        return '\n'.join(headers[arch]) + '\n'
    else:
        return ''

def _bfdname(arch):
    bfdnames = {
        'i386'    : 'elf32-i386',
        'amd64'   : 'elf64-x86-64',
        'arm'     : 'elf32-littlearm',
        'thumb'   : 'elf32-littlearm',
        'mips'    : 'elf32-%smips' % context.endianness,
        'alpha'   : 'elf64-alpha',
        'cris'    : 'elf32-cris',
        'ia64'    : 'elf64-ia64-little',
        'm68k'    : 'elf32-m68k',
        'powerpc' : 'elf32-powerpc',
        'vax'     : 'elf32-vax',
    }

    if arch in bfdnames:
        return bfdnames[arch]
    else:
        error("Cannot find bfd name for architecture %r" % arch)


def _bfdarch(arch):
    if arch == 'amd64':
        return 'i386:x86-64'
    elif arch == 'thumb':
        return 'arm'
    elif arch == 'ia64':
        return 'ia64-elf64'
    else:
        return arch


def _run(cmd, stdin = None):
    try:
        proc = subprocess.Popen(
            cmd,
            stdin  = subprocess.PIPE,
            stdout = subprocess.PIPE,
            stderr = subprocess.PIPE
        )
        stdout, stderr = proc.communicate(stdin)
        exitcode = proc.wait()
    except OSError as e:
        if e.errno == errno.ENOENT:
            error('Could not run %r the program' % cmd[0])
        else:
            raise

    if (exitcode, stderr) != (0, ''):
        msg = 'There was an error running %s:\n' % repr(cmd[0])
        if exitcode != 0:
            msg += 'It had the exitcode %d.\n' % exitcode
        if stderr != '':
            msg += 'It had this on stdout:\n%s\n' % stderr
        error(msg)


    return stdout

def cpp(shellcode, arch = None, os = None):
    """cpp(shellcode, arch = None, os = None) -> str

    Runs CPP over the given shellcode.

    The output will always contain exactly one newline at the end.

    Examples:
      >>> cpp("testing: SYS_setresuid")
      'testing: SYS_setresuid\\n'
      >>> cpp("mov al, SYS_setresuid", arch = "i386", os = "linux")
      'mov al, 164\\n'
      >>> cpp("weee SYS_setresuid", arch = "arm", os = "linux")
      'weee (0x900000+164)\\n'
      >>> cpp("SYS_setresuid", arch = "thumb", os = "linux")
      '(0+164)\\n'
      >>> cpp("SYS_setresuid", os = "freebsd")
      '311\\n'
    """

    arch = arch or context.arch
    os   = os   or context.os
    code = _include_header(arch, os) + shellcode
    cmd  = [
        'cpp',
        '-C',
        '-nostdinc',
        '-undef',
        '-P',
        '-I' + _incdir,
        '/dev/stdin'
    ]
    return _run(cmd, code).strip('\n').rstrip() + '\n'


def asm(shellcode, arch = None, os = None):
    """asm(code, arch = None, os = None) -> str

    Runs CPP over a given shellcode and then assembles it into bytes.

    To see which architectures or operating systems are supported,
    look in :mod:`pwnlib.contex`.

    To support all these architecture, we bundle the GNU assembler
    and objcopy with pwntools.

    Args:
      shellcode(str): Assembler code to assemble.
      arch: A supported architecture or None. In case of None,
            :data:`pwnlib.context.arch` will be used.
      os: A supported operating system or None. In case of None,
          :data:`pwnlib.context.os` will be used.

    Examples:
      >>> asm("mov eax, SYS_select", arch = 'i386', os = 'freebsd')
      '\\xb8]\\x00\\x00\\x00'
      >>> asm("mov rax, SYS_select", arch = 'amd64', os = 'linux')
      '\\xb8\\x17\\x00\\x00\\x00'
      >>> asm("ldr r0, =SYS_select", arch = 'arm', os = 'linux')
      '\\x04\\x00\\x1f\\xe5R\\x00\\x90\\x00'
    """

    arch = arch or context.arch
    os   = os   or context.os
    if not arch:
        raise ValueError(
            "asm() needs to get 'arch' through an argument or the context"
        )

    assembler = _assembler(arch)
    objcopy   = [_objcopy(arch), '-j.shellcode', '-Obinary']
    code      = _arch_header(arch) + cpp(shellcode, arch, os)


    tmpdir    = tempfile.mkdtemp(prefix = 'pwn-asm-')
    step1     = path.join(tmpdir, 'step1')
    step2     = path.join(tmpdir, 'step2')
    step3     = path.join(tmpdir, 'step3')

    try:
        with open(step1, 'w') as fd:
            fd.write(code)

        _run(assembler + ['-o', step2, step1])

        if arch in ['i386', 'amd64']:
            with open(step2) as fd:
                return fd.read()

        # Sanity check for seeing if the output has relocations
        relocs = subprocess.check_output(
            ['readelf', '-r', step2]
        ).strip()
        if len(relocs.split('\n')) > 1:
            raise Exception(
                'There were relocations in the shellcode:\n\n%s' % relocs
            )

        _run(objcopy + [step2, step3])

        with open(step3) as fd:
            return fd.read()
    except:
        error("An error occurred while assembling:\n%s" % code)
    finally:
        shutil.rmtree(tmpdir)

def disasm(data, arch = None, vma = 0):
    """disasm(data, arch = None) -> str

    Disassembles a bytestring into human readable assembler.

    To see which architectures are supported,
    look in :mod:`pwnlib.contex`.

    To support all these architecture, we bundle the GNU objcopy
    and objdump with pwntools.

    Args:
      data(str): Bytestring to disassemble.
      arch: A supported architecture or None. In case of None,
            :data:`pwnlib.context.arch` will be used.
      vma(int): Passed through to the --adjust-vma argument of objdump

    Examples:
      >>> print disasm('b85d000000'.decode('hex'), arch = 'i386')
         0:   b8 5d 00 00 00          mov    eax,0x5d
      >>> print disasm('b817000000'.decode('hex'), arch = 'amd64')
         0:   b8 17 00 00 00          mov    eax,0x17
      >>> print disasm('04001fe552009000'.decode('hex'), arch = 'arm')
         0:   e51f0004        ldr     r0, [pc, #-4]   ; 0x4
         4:   00900052        addseq  r0, r0, r2, asr r0
      >>> print disasm('4ff00500'.decode('hex'), arch = 'thumb')
         0:   f04f 0005       mov.w   r0, #5
    """

    arch = arch or context.arch
    if not arch:
        raise ValueError(
            "asm() needs to get 'arch' through an argument or the context"
        )

    tmpdir = tempfile.mkdtemp(prefix = 'pwn-disasm-')
    step1     = path.join(tmpdir, 'step1')
    step2     = path.join(tmpdir, 'step2')

    bfdarch = _bfdarch(arch)
    bfdname = _bfdname(arch)
    objdump = _objdump(arch) + ['-d', '--adjust-vma', str(vma)]
    objcopy = [
        _objcopy(arch),
        '-I', 'binary',
        '-O', bfdname,
        '-B', bfdarch,
        '--set-section-flags', '.data=code',
        '--rename-section', '.data=.text',
    ]

    if arch == 'thumb':
        objcopy += ['--prefix-symbol=$t.']
    else:
        objcopy += ['-w', '-N', '*']

    try:
        with open(step1, 'w') as fd:
            fd.write(data)
        _run(objcopy + [step1, step2])

        output0 = subprocess.check_output(objdump + [step2])
        output1 = output0.split('<.text>:\n')
        if len(output1) != 2:
            raise IOError(
                'Something went wrong with objdump:\n\n%s' % output0
            )
        else:
            return output1[1].strip('\n').rstrip().expandtabs()
    finally:
        shutil.rmtree(tmpdir)
