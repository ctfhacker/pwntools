from .. import log
from ..util.misc import sh_string
from . import tube
import subprocess, fcntl, os, select, pexpect

# Compatibility between popen and pexpect.spawn
pexpect.spawn.returncode = property(lambda self: self.exitstatus)

class process(tube.tube):
    def __init__(self, args, shell = False, executable = None,
                 cwd = None, env = None, timeout = 'default', pty=False):
        """Launches a process, in the same fashion as `popen`, but permits
        interaction with the process as a tube.

        Arguments:
            args(tuple): Passed through to subprocess.Popen.
            shell(bool): Passed through to subprocess.Popen.
            executable(str): Passed through to subprocess.Popen.
            cwd(str): Passed through to subprocess.Popen.
            env(dict): Passed through to subprocess.Popen.
            timeout(float): Passed through to tube.__init__
            tty(bool): If True, PTY is created and assiged to
                stdin/stdout/stderr of the process.
        """
        super(process, self).__init__(timeout)

        if executable:
            self.program = executable
        elif isinstance(args, (str, unicode)):
            self.program = args
        elif isinstance(args, (list, tuple)):
            self.program = args[0]
        else:
            log.error("process(): Do not understand the arguments %r" % args)

        stdin = stdout = subprocess.PIPE
        stderr = subprocess.STDOUT

        if pty:
            if isinstance(args, (list, tuple)):
                args = ['-c', subprocess.list2cmdline(args)]

            print args
            self.proc  = pexpect.spawn('/bin/sh', args,
                                       cwd  = cwd or '.',
                                       env  = env or os.environ,
                                       echo = False)
            self.proc.poll  = lambda: spawn_poll(self.proc)
            self.proc.stdin = self.proc.stdout = os.fdopen(self.proc.child_fd, 'r+')

        else:
            self.proc  = subprocess.Popen(args,
                                          shell      = shell,
                                          executable = executable,
                                          cwd        = cwd,
                                          env        = env,
                                          stdin      = stdin,
                                          stdout     = stdout,
                                          stderr     = stderr)

        self.stop_noticed = False

        # Set in non-blocking mode so that a call to call recv(1000) will
        # return as soon as a the first byte is available
        fd = self.proc.stdout.fileno()
        fl = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

        log.success("Started program %r" % self.program)

    def kill(self):
        """kill()

        Kills the process.
        """

        self.close()

    def poll(self):
        """poll() -> int

        Poll the exit code of the process. Will return None, if the
        process has not yet finished and the exit code otherwise.
        """
        self.proc.poll()
        if self.proc.returncode != None and not self.stop_noticed:
            self.stop_noticed = True
            log.info("Program %r stopped with exit code %d" % (self.program, self.proc.returncode))

        return self.proc.returncode

    def communicate(self, stdin = None):
        """communicate(stdin = None) -> str

        Calls :meth:`subprocess.Popen.communicate` method on the process.
        """

        return self.proc.communicate(stdin)

    # Implementation of the methods required for tube
    def recv_raw(self, numb):
        # This is a slight hack. We try to notice if the process is
        # dead, so we can write a message.
        self.poll()

        if self.proc.stdout.closed:
            raise EOFError

        if not self.can_recv_raw(self.timeout):
            return None

        # This will only be reached if we either have data,
        # or we have reached an EOF. In either case, it
        # should be safe to read without expecting it to block.
        data = self.proc.stdout.read(numb)

        if data == '':
            self.proc.stdout.close()
            raise EOFError
        else:
            return data

    def send_raw(self, data):
        # This is a slight hack. We try to notice if the process is
        # dead, so we can write a message.
        self.poll()

        if self.proc.stdin.closed:
            raise EOFError

        try:
            self.proc.stdin.write(data)
            self.proc.stdin.flush()
        except IOError:
            raise # raise EOFError

    def settimeout_raw(self, timeout):
        pass

    def can_recv_raw(self, timeout):
        if timeout == None:
            return select.select([self.proc.stdout], [], []) == ([self.proc.stdout], [], [])
        else:
            return select.select([self.proc.stdout], [], [], timeout) == ([self.proc.stdout], [], [])

    def connected_raw(self, direction):
        if direction == 'any':
            return self.poll() == None
        elif direction == 'send':
            return not self.proc.stdout.closed
        elif direction == 'recv':
            return not self.proc.stdin.closed

    def close(self):
        # First check if we are already dead
        self.poll()

        if not self.stop_noticed:
            try:
                self.proc.kill()
                self.stop_noticed = True
                log.info('Stopped program %r' % self.program)
            except OSError:
                pass


    def fileno(self):
        if not self.connected():
            log.error("A stopped program does not have a file number")

        return self.proc.stdout.fileno()

    def shutdown_raw(self, direction):
        if direction == "send":
            self.proc.stdin.close()

        if direction == "recv":
            self.proc.stdout.close()

        if False not in [self.proc.stdin.closed, self.proc.stdout.closed]:
            self.close()
