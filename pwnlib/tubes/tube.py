from .buffer import Buffer
from .timeout import Timeout
from .. import context, term, atexit
from ..util import misc
from ..context import context
import re, threading, sys, time, subprocess, logging

log = logging.getLogger(__name__)

class tube(Timeout):
    """
    Container of all the tube functions common to sockets, TTYs and SSH connetions.
    """

    def __init__(self, timeout=None):
        super(tube, self).__init__()
        self.buffer          = Buffer()
        atexit.register(self.close)

    # Functions based on functions from subclasses
    def recv(self, numb = sys.maxint, timeout = None):
        """recv(numb = sys.maxint, timeout = None) -> str

        Receives up to `numb` bytes of data from the tube, and returns
        as soon as any quantity of data is available.

        Raises:
            :exc:`exceptions.EOFError` The connection is closed

        Returns:
            A string containing bytes received from the socket,
            or ``''`` if a timeout occurred while waiting.
        """
        return self._recv(numb, timeout) or ''

    def unrecv(self, data):
        """unrecv(data)

        Puts the specified data back at the beginning of the receive
        buffer.

        Examples:

            >>> t = tube()
            >>> t.recv_raw = lambda: 'hello'
            >>> t.recv()
            'hello'
            >>> t.recv()
            'hello'
            >>> t.unrecv('world')
            >>> t.recv()
            'world'
            >>> t.recv()
            'hello'
        """
        self.buffer.unget(data)

    def _fill(self, timeout = None):
        """_fill(timeout = None)

        Fills the internal buffer from the pipe
        """

        with self.timeout_scope(timeout):
            data = self.recv_raw(sys.maxint)

        if data:
            log.debug('Received %#x bytes:' % len(data))
            for line in data.splitlines(True):
                log.indented(repr(line), level=logging.DEBUG)

        self.buffer.add(data)
        return data


    def _recv(self, numb = sys.maxint, timeout = None):
        """_recv(numb = sys.maxint, timeout = None) -> str

        Recieves one chunk of from the internal buffer or from the OS if the
        buffer is empty.
        """
        data = ''

        # No buffered data, could not put anything in the buffer
        # before timeout.
        if not self.buffer and not self._fill(numb,timeout):
            return None

        return self.buffer.get(numb)

    def recvpred(self, pred, timeout = None):
        """recvpred(pred, timeout = None) -> str

        Receives one byte at a time from the tube, until ``pred(bytes)``
        evaluates to True.

        If the request is not satisfied before ``timeout`` seconds pass,
        all data is buffered and an empty string (``''``) is returned.

        Arguments:
            pred(callable): Function to call, with the currently-accumulated data.
            timeout(int): Timeout for the operation

        Raises:
            :exc:`exceptions.EOFError` The connection is closed

        Returns:
            A string containing bytes received from the socket,
            or ``''`` if a timeout occurred while waiting.


        """

        data = ''

        with self.timeout_scope(timeout):
            while not pred(data):
                try:
                    res = self.recv(1)
                except:
                    self.unrecv(data)
                    return ''

                if res:
                    data += res
                else:
                    self.unrecv(data)
                    return ''

        return data

    def recvn(self, numb, timeout = None):
        """recvn(numb, timeout = None) -> str

        Recieves exactly `n` bytes.

        If the request is not satisfied before ``timeout`` seconds pass,
        all data is buffered and an empty string (``''``) is returned.

        Raises:
            :exc:`exceptions.EOFError` The connection is closed

        Returns:
            A string containing bytes received from the socket,
            or ``''`` if a timeout occurred while waiting.

        Examples:

            >>> t = tube()
            >>> data = 'hello world'
            >>> t.recv_raw = lambda n: data
            >>> t.recvn(len(data)) == data
            True
            >>> t.recvn(len(data)+1) == data + data[0]
            >>> t.recv_raw = None
            >>> t.recv() = data[1:]
        """

        # Keep track of how much data has been received
        # It will be pasted together at the end if a
        # timeout does not occur, or put into the tube buffer.
        with self.timeout_scope(timeout):
            while len(self.buffer) < numb:
                self._fill(numb,timeout)

        return self.buffer.get(numb)

    def recvuntil(self, delims, drop=False, timeout = None):
        """recvuntil(delims, timeout = None) -> str

        Recieve data until one of `delims` is encountered.

        If the request is not satisfied before ``timeout`` seconds pass,
        all data is buffered and an empty string (``''``) is returned.

        arguments:
            delims(str,tuple): String of delimiters characters, or list of delimiter strings.
            drop(bool): Drop the ending.  If ``True`` it is removed from the end of the return value.

        Raises:
            :exc:`exceptions.EOFError` The connection is closed

        Returns:
            A string containing bytes received from the socket,
            or ``''`` if a timeout occurred while waiting.

        Examples:

            >>> t = tube()
            >>> t.recv_raw = lambda: "Hello World!"
            >>> t.recvuntil(' ')
            'Hello '
        """

        # Convert string into list of characters
        delims = tuple(delims)

        expr = re.compile('%s' % '|'.join(map(re.escape, delims)))
        data = ''
        while True:
            try:
                res = self.recv(timeout = timeout)
            except:
                self.unrecv(data)
                raise

            if data:
                data += res
            if not res:
                self.unrecv(data)
                return ''

            match = expr.search(data)
            if match:
                self.unrecv(data[match.endpos:])
                return data[:match.endpos]

    def recvlines(self, numlines=sys.maxint, keep = False, timeout = None):
        r"""recvlines(numlines = sys.maxint, keep = False, timeout = None) -> str list

        Recieve up to ``numlines`` lines.

        If the request is not satisfied before ``timeout`` seconds pass,
        all data is buffered and an empty string (``''``) is returned.

        Arguments:
            numlines(int): Maximum number of lines to receive
            keep(bool): Keep newlines at the end of each line
            timeout(int): Maximum timeout

        Returns:
            A list of lines received

        Examples:

            >>> t = tube()
            >>> t.recv_raw = lambda: '\n'
            >>> t.recvlines(3)
            ['', '', '']
            >>> t.recv_raw = lambda: 'Foo\nBar\nBaz\n'
            >>> t.recvlines(3)
            ['Foo', 'Bar', 'Baz']
            >>> t.recvlines(3, True)
            ['Foo\n', 'Bar\n', 'Baz\n']
        """
        lines = []
        with self.timeout_scope(timeout):
            for _ in xrange(numlines):
                try:
                    res = self.recvline(keep=True, timeout=timeout)
                except:
                    self.unrecv(''.join(lines))
                    raise

                if res:
                    lines.append(res)
                else:
                    break

        if not keep:
            lines = [lines.rstrip('\n') for line in lines]

        return lines

    def recvline(self, keep = False, timeout = None):
        r"""recvline(keep = False) -> str

        Receive a single line from the tube.

        If the request is not satisfied before ``timeout`` seconds pass,
        all data is buffered and an empty string (``''``) is returned.

        Arguments:
            keep(bool): Keep the line ending
            timeout(int): Timeout

        Return:
            All bytes received over the tube until the first
            newline ``'\n'`` is received.  Optionally retains
            the ending.
        """
        return self.recvuntil('\n', drop = not keep, timeout = timeout)

    def recvline_pred(self, pred, keep = False, timeout = None):
        r"""recvline_pred(pred, keep = False) -> str

        Receive data until ``pred(line)`` returns a truthy value.
        Drop all other data.

        If the request is not satisfied before ``timeout`` seconds pass,
        all data is buffered and an empty string (``''``) is returned.

        Arguments:
            pred(callable): Function to call.  Returns the line for which
                this function returns ``True``.

        Examples:

            >>> t = tube()
            >>> t.recv_raw = lambda: "Foo\nBar\nBaz\n"
            >>> t.recvline_pred(lambda line: line == "Bar")
        """

        tmpbuf = Buffer()
        line   = ''
        with self.timeout_scope(timeout):
            while True:
                try:
                    line = self.recvline('\n', keep=True)
                except:
                    self.buffer.add(tmpbuf)
                    raise

                if not line:
                    self.buffer.add(tmpbuf)
                    return ''

                elif not pred(line.rstrip):
                    tmpbuf.add(line)

                break


        if keep:
            return line

        return line.rstrip('\n')

    def recvline_startswith(self, delims, keep = False, timeout = None):
        """recvline_startswith(delims, keep = False, timeout = None) -> str

        Keep recieving lines until one is found that starts with one of
        `delims`.  Returns the last line recieved.

        If the request is not satisfied before ``timeout`` seconds pass,
        all data is buffered and an empty string (``''``) is returned.

        Arguments:
            delims(str,tuple): List of strings to search for, or string of single characters
            keep(bool): Return lines with newlines if ``True``
            timeout(int): Timeout, in seconds

        Returns:
            The first line received which starts with a delimiter in ``delims``.

        Examples:

            >>> t = tube()
            >>> t.recv_raw = lambda: "Hello\nWorld\nXylophone\n"
            >>> t.recvline_startswith('WXYZ')
            'World'
            >>> t.recvline_startswith('WXYZ', True)
            'Xylophone\n'
        """
        return recvline_pred(lambda line: any(map(line.startswith, tuple(delims))),
                             keep=keep,
                             timeout=timeout)

    def recvline_endswith(self, delims, keep = False, timeout = None):
        """recvline_endswith(delims, keep = False, timeout = None) -> str

        Keep recieving lines until one is found that starts with one of
        `delims`.  Returns the last line recieved.

        If the request is not satisfied before ``timeout`` seconds pass,
        all data is buffered and an empty string (``''``) is returned.

        See :meth:`recvline_startswith` for more details.

        Examples:

            >>> t = tube()
            >>> t.recv_raw = lambda: 'Foo\nBar\nBaz\nKaboodle\n'
            >>> t.recvline_endswith('r')
            'Bar'
            >>> t.recvline_endswth('abcde', True)
            'Kaboodle\n'
        """
        return recvline_pred(lambda line: any(map(line.endswith, tuple(delims))),
                             keep=keep,
                             timeout=timeout)

    def recvregex(self, regex, exact = False, timeout = None):
        """recvregex(regex, exact = False, timeout = None) -> str

        Wrapper around :func:`recvpred`, which will return when a regex
        matches the string in the buffer.

        By default :func:`re.RegexObject.search` is used, but if `exact` is
        set to True, then :func:`re.RegexObject.match` will be used instead.

        If the request is not satisfied before ``timeout`` seconds pass,
        all data is buffered and an empty string (``''``) is returned.
        """

        if isinstance(regex, (str, unicode)):
            regex = re.compile(regex)

        if exact:
            pred = regex.match
        else:
            pred = regex.search

        return self.recvpred(pred, timeout = timeout)

    def recvline_regex(self, regex, exact = False, keep = False, timeeout = None):
        """recvregex(regex, exact = False, keep = False,
                     timeout = None) -> str

        Wrapper around :func:`recvline_pred`, which will return when a regex
        matches a line.

        By default :func:`re.RegexObject.search` is used, but if `exact` is
        set to True, then :func:`re.RegexObject.match` will be used instead.

        If the request is not satisfied before ``timeout`` seconds pass,
        all data is buffered and an empty string (``''``) is returned.
        """

        if isinstance(regex, (str, unicode)):
            regex = re.compile(regex)

        if exact:
            pred = regex.match
        else:
            pred = regex.search

        return self.recvline_pred(pred, keep = keep, timeout = timeout)

    def recvrepeat(self, timeout = None):
        """recvrepeat()

        Receives data until a timeout or EOF is reached.
        """

        with self.timeout_scope(timeout):
            while self._fill():
                pass

        return self.buffer.get()

    def recvall(self):
        """recvall() -> str

        Receives data until EOF is reached.
        """

        h = log.waitfor('Recieving all data')

        l = len(self.buffer)
        with self.timeout_scope('inf'):
            data = 'yay truthy strings'

            while data:
                try:
                    data = self._fill()
                except EOFError:
                    break
                l += len(data)
                h.status(misc.size(l))

        h.success("Done (%s)" % misc.size(l))

        return self.buffer.get()

    def send(self, data):
        """send(data)

        Sends data. Will also print a debug message with
        log level :data:`pwnlib.log_levels.DEBUG` about it.

        If it is not possible to send anymore because of a closed
        connection, it raises and :exc:`exceptions.EOFError`.
        """

        log.debug('Sent %#x bytes:' % len(data))
        for line in data.splitlines(True):
            log.indent(repr(line), level=logging.DEBUG)
        self.send_raw(data)

    def sendline(self, line):
        r"""sendline(data)

        Shorthand for ``send(data + '\n')``.
        """

        self.send(line + '\n')

    def sendafter(self, delim, data, timeout = None):
        """sendafter(delim, data, timeout = None) -> str

        A combination of ``recvuntil(delim, timeout)`` and ``send(data)``."""

        res = self.recvuntil(delim, timeout)
        self.send(data)
        return res

    def sendlineafter(self, delim, data, timeout = None):
        """sendlineafter(delim, data, timeout = None) -> str

        A combination of ``recvuntil(delim, timeout)`` and ``sendline(data)``."""

        res = self.recvuntil(delim, timeout)
        self.sendline(data)
        return res

    def sendthen(self, delim, data, timeout = None):
        """sendthen(delim, data, timeout = None) -> str

        A combination of ``send(data)`` and ``recvuntil(delim, timeout)``."""

        self.send(data)
        return self.recvuntil(delim, timeout)

    def sendlinethen(self, delim, data, timeout = None):
        """sendlinethen(delim, data, timeout = None) -> str

        A combination of ``sendline(data)`` and ``recvuntil(delim, timeout)``."""

        self.send(data + '\n')
        return self.recvuntil(delim, timeout)

    def interactive(self, prompt = term.text.bold_red('$') + ' '):
        """interactive(prompt = pwnlib.term.text.bold_red('$') + ' ')

        Does simultaneous reading and writing to the tube. In principle this just
        connects the tube to standard in and standard out, but in practice this
        is much more usable, since we are using :mod:`pwnlib.term` to print a
        floating prompt.

        Thus it only works in while in :data:`pwnlib.term.term_mode`.
        """

        log.info('Switching to interactive mode')

        go = threading.Event()
        def recv_thread():
            while not go.isSet():
                try:
                    cur = self.recv(timeout = 0.05)
                    if cur:
                        sys.stdout.write(cur)
                        sys.stdout.flush()
                except EOFError:
                    log.info('Got EOF while reading in interactive')
                    break

        t = context.thread(target = recv_thread)
        t.daemon = True
        t.start()

        try:
            while not go.isSet():
                if term.term_mode:
                    data = term.readline.readline(prompt = prompt, float = True)
                else:
                    data = sys.stdin.read(1)

                if data:
                    try:
                        self.send(data)
                    except EOFError:
                        go.set()
                        log.info('Got EOF while sending in interactive')
                else:
                    go.set()
        except KeyboardInterrupt:
            log.info('Interrupted')
            go.set()

        while t.is_alive():
            t.join(timeout = 0.1)

    def clean(self, timeout = 0.05):
        """clean(timeout = 0.05)

        Removes all the buffered data from a tube by calling
        :meth:`pwnlib.tubes.tube.tube.recv` with a low timeout until it fails.
        """

        self.recvrepeat(timeout = timeout)

    def clean_and_log(self, timeout = 0.05):
        """clean_and_log(timeout = 0.05)

        Works exactly as :meth:`pwnlib.tubes.tube.tube.clean`, but logs recieved
        data with :meth:`pwnlib.log.info`.
        """

        if self.connected():
            log.info('Cleaning tube (fileno = %d):' % self.fileno())
            log.indented(self.recvrepeat(timeout = timeout))

    def connect_input(self, other):
        """connect_input(other)

        Connects the input of this tube to the output of another tube object."""

        def pump():
            import sys as _sys
            while True:
                if not (self.connected('send') and other.connected('recv')):
                    break

                try:
                    data = other.recv(timeout = 0.05)
                except EOFError:
                    break

                if not _sys:
                    return

                if data == None:
                    continue

                try:
                    self.send(data)
                except EOFError:
                    break

                if not _sys:
                    return

            self.shutdown('send')
            other.shutdown('recv')

        t = context.thread(target = pump)
        t.daemon = True
        t.start()

    def connect_output(self, other):
        """connect_output(other)

        Connects the output of this tube to the input of another tube object."""

        other.connect_input(self)

    def connect_both(self, other):
        """connect_both(other)

        Connects the both ends of this tube object with another tube object."""

        self.connect_input(other)
        self.connect_output(other)

    def spawn_process(self, *args, **kwargs):
        """Spawns a new process having this tube as stdin, stdout and stderr.

        Takes the same arguments as :class:`subprocess.Popen`."""

        subprocess.Popen(
            *args,
            stdin = self.fileno(),
            stdout = self.fileno(),
            stderr = self.fileno(),
            **kwargs
        )

    def __lshift__(self, other):
        self.connect_input(other)
        return other

    def __rshift__(self, other):
        self.connect_output(other)
        return other

    def __ne__(self, other):
        self << other << self

    def wait_for_close(self):
        """Waits until the tube is closed."""

        while self.connected():
            time.sleep(0.05)

    def can_recv(self, timeout = 0):
        """can_recv(timeout = 0) -> bool

        Returns True, if there is data available within `timeout` seconds."""

        return bool(self.buffer or self.can_recv_raw(timeout))

    def settimeout(self, timeout):
        """settimeout(timeout)

        Set the timeout for receiving operations. If the string "default"
        is given, then :data:`context.timeout` will be used. If None is given,
        then there will be no timeout.
        """

        self.timeout = timeout
        self.settimeout_raw(self.timeout)

    def shutdown(self, direction = "send"):
        """shutdown(direction = "send")

        Closes the tube for futher reading or writing depending on `direction`.

        Args:
          direction(str): Which direction to close; "in", "read" or "recv"
            closes the tube in the ingoing direction, "out", "write" or "send"
            closes it in the outgoing direction.

        Returns:
          :const:`None`
        """

        if   direction in ('in', 'read', 'recv'):
            direction = 'recv'
        elif direction in ('out', 'write', 'send'):
            direction = 'send'
        else:
            log.error('direction must be "in", "read" or "recv", or "out", "write" or "send"')

        self.shutdown_raw(direction)

    def connected(self, direction = 'any'):
        """connected(direction = 'any') -> bool

        Returns True if the tube is connected in the specified direction.

        Args:
          direction(str): Can be the string 'any', 'in', 'read', 'recv',
                          'out', 'write', 'send'.
        """

        if   direction in ('in', 'read', 'recv'):
            direction = 'recv'
        elif direction in ('out', 'write', 'send'):
            direction = 'send'
        elif direction == 'any':
            pass
        else:
            log.error('direction must be "any", "in", "read" or "recv", or "out", "write" or "send"')

        return self.connected_raw(direction)

    def __enter__(self):
        """Permit use of 'with' to control scoping and closing sessions.

        >>> shell = ssh(host='bandit.labs.overthewire.org',user='bandit0',password='bandit0') # doctest: +SKIP
        >>> with shell.run('bash') as s:  # doctest: +SKIP
        ...     s.sendline('echo helloworld; exit;')
        ...     print 'helloworld' in s.recvall()
        ...
        True
        """
        return self

    def __exit__(self, type, value, traceback):
        """Handles closing for 'with' statement"""
        self.close()

    # The minimal interface to be implemented by a child
    def recv_raw(self, numb):
        """recv_raw(numb) -> str

        Should not be called directly. Receives data without using the buffer
        on the object.

        Unless there is a timeout or closed connection, this should always
        return data. In case of a timeout, it should return None, in case
        of a closed connection it should raise an :exc:`exceptions.EOFError`.
        """

        raise EOFError('Not implemented')

    def send_raw(self, data):
        """send_raw(data)

        Should not be called directly. Sends data to the tube.

        Should return :exc:`exceptions.EOFError`, if it is unable to send any
        more, because of a close tube.
        """

        raise EOFError('Not implemented')

    def settimeout_raw(self, timeout):
        """settimeout_raw(timeout)

        Should not be called directly. Sets the timeout for
        the tube.
        """

        raise NotImplementedError()

    def timeout_change(self, timeout):
        """
        Informs the raw layer of the tube that the timeout has changed.

        Should not be called directly.

        Inherited from :class:`Timeout`.
        """
        try:
            self.settimeout_raw(timeout)
        except NotImplementedError:
            pass

    def can_recv_raw(self, timeout):
        """can_recv_raw(timeout) -> bool

        Should not be called directly. Returns True, if
        there is data available within the timeout, but
        ignores the buffer on the object.
        """

        raise NotImplementedError()

    def connected_raw(self, direction):
        """connected(direction = 'any') -> bool

        Should not be called directly.  Returns True iff the
        tube is connected in the given direction.
        """

        raise NotImplementedError()

    def close(self):
        """close()

        Closes the tube.
        """

        raise NotImplementedError()

    def fileno(self):
        """fileno() -> int

        Returns the file number used for reading.
        """

        raise NotImplementedError()

    def shutdown_raw(self, direction):
        """shutdown_raw(direction)

        Should not be called directly.  Closes the tube for further reading or
        writing.
        """

        raise NotImplementedError()
