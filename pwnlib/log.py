"""The purpose of this module is to expose a nice API
to wrap around :func:`pwnlib.term.output`.

We have designed it around these considerations:

* It should work both in :data:`pwnlib.term.term_mode` and in normal mode.
* We want log levels.
* We want spinners.
* It should expose all the functionality of :func:`pwnlib.term.output`.

For an explanations of the semantics of the ``frozen``, ``float``, ``priority`` and ``indent``
arguments, see :func:`pwnlib.term.output`.
"""

__all__ = [
    # loglevel == DEBUG
    'debug',

    # loglevel == INFO
    'info', 'success', 'failure', 'warning', 'indented',

    # loglevel == ERROR
    'error', 'bug', 'fatal',

    # spinner-functions (loglevel == INFO)
    'waitfor', 'status', 'done_success', 'done_failure',
]

import threading, sys, time, random, warnings, traceback, collections
from .context import context, _Thread
from . import term, log_levels, exception
from .term import text, spinners

import logging

class Logger(logging.Logger):
    def __init__(self, *args, **kwargs):
        super(Logger, self).__init__(*args, **kwargs)
    def getEffectiveLevel(self):
        return context.log_level
    def setLevel(self, lvl):
        context.log_level = lvl

class TermHandler(logging.Handler):
    def emit(self, record):
        _put(log_level)

class StdoutHandler(logging.Handler):
    """
    For no apparent reason, logging.StreamHandler(sys.stdout)
    breaks all of the fancy output formatting.

    So we bolt this on.
    """
    def emit(self, record):
        self.acquire()
        msg = self.format(record)
        sys.stdout.write('%s\n' % msg)
        self.release()


class TermPrefixIndentFormatter(logging.Formatter):
    """
    Logging formatter which performs prefixing based on a pwntools-
    specific key, as well as indenting all secondary lines.
    """
    def __init__(self,*args,**kwargs):
        super(TermColorIndentFormatter, self).__init__(*args,**kwargs)

    def format(self, record):
        msg = super(TermColorIndentFormatter, self).format(record)

        try: msg = record.pwn_prefix + msg
        except AttributeError: raise

        msg = nlindent.join(msg.splitlines())

        return msg

indent    = '    '
nlindent  = '\n' + indent
logger    = Logger('pwn')
console   = StdoutHandler()
console.setFormatter(TermColorIndentFormatter('%(message)s'))
logger.addHandler(console)

def indented(msg):  logger.info(msg,    extra={'pwn_prefix': indent})
def error(msg):     logger.error(msg,   extra={'pwn_prefix': '[' + text.bold_red('-')     + '] '})
def warn(msg):      logger.warning(msg, extra={'pwn_prefix': '[' + text.bold_yellow('!')  + '] '})
def info(msg):      logger.info(msg,    extra={'pwn_prefix': '[' + text.bold_blue('+')    + '] '})
def success(msg):   logger.info(msg,    extra={'pwn_prefix': '[' + text.bold_green('+')   + '] '})
def failure(msg):   logger.info(msg,    extra={'pwn_prefix': '[' + text.on_red('-')       + '] '})
def debug(msg):     logger.debug(msg,   extra={'pwn_prefix': '[' + text.bold_red('DEBUG') + '] '})

def bug(msg):       raise Exception(msg)
def fatal(msg):     raise SystemExit(msg)
warning = warn


#******************************************************************************
#                               LEGACY PAST HERE
#******************************************************************************


_lock = threading.Lock()
_last_was_nl = True
def _put(log_level, string = '', frozen = True, float = False, priority = 10, indent = 0):
    global _last_was_nl
    if context.log_level > log_level:
        return _dummy_handle
    elif term.term_mode:
        return term.output(str(string), frozen = frozen, float = float,
                           priority = priority, indent = indent)
    else:
        string = str(string)
        if not string:
            return _dummy_handle
        if _last_was_nl:
            string = ' ' * indent + string
            _last_was_nl = False
        if string[-1] == '\n':
            _last_was_nl = True
        if indent:
            string = string[:-1].replace('\n', '\n' + ' ' * indent) + string[-1]
        sys.stderr.write(string)
        return _dummy_handle

class _DummyHandle(object):
    def update(self, _string):
        pass

    def freeze(self):
        pass

    def delete(self):
        pass
_dummy_handle = _DummyHandle()


_waiter_stack = []
class _Waiter(object):
    def _remove(self):
        while self in _waiter_stack:
            _waiter_stack.remove(self)

class _DummyWaiter(_Waiter):
    def status(self, _):
        pass

    def success(self, string = 'OK'):
        pass

    def failure(self, string = 'FAILED!'):
        pass

class _SimpleWaiter(_Waiter):
    def __init__(self, msg, _spinner, log_level):
        self.log_level = log_level
        info('%s...' % msg, log_level = self.log_level)
        self.msg = msg
        self.last_update = 0

    def status(self, string):
        t = time.time()
        if self.last_update + 1 <= t:
            self.last_update = t
            info('%s: %s' % (self.msg, string), log_level = self.log_level)

    def success(self, string = 'OK'):
        success('%s: %s' % (self.msg, string), log_level = self.log_level)
        self._remove()

    def failure(self, string = 'FAILED!'):
        failure('%s: %s' % (self.msg, string), log_level = self.log_level)
        self._remove()


class _Spinner(_Thread):
    def __init__(self, spinner, log_level):
        super(_Spinner, self).__init__()
        self.spinner = spinner
        self.idx = 0
        self.daemon = True
        self.sys = sys
        self.handle = _put(log_level, '', frozen = False)
        self.lock = threading.Lock()
        self.running = True
        self.start()

    def run(self):
        while True:
            # interpreter shutdown
            if not self.sys:
                break
            with self.lock:
                if self.running:
                    self.handle.update(
                        text.bold_blue(self.spinner[self.idx])
                        )
                else:
                    break
            self.idx = (self.idx + 1) % len(self.spinner)
            time.sleep(0.1)

    def stop(self, string):
        self.running = False
        with self.lock:
            self.handle.update(string)
            self.handle.freeze()


class _TermWaiter(_Waiter):
    def __init__(self, msg, spinner, log_level):
        with _lock:
            self.hasmsg = msg != ''
            _put(log_level, '[')
            if spinner is None:
                spinner = random.choice(spinners.spinners)
            self.spinner = _Spinner(spinner, log_level)
            _put(log_level, '] %s' % msg)
            self.stat = _put(log_level, '', frozen = False)
            _put(log_level, '\n')

    def status(self, string):
        if self.hasmsg and string:
            string = ': ' + string
        self.stat.update(string)

    def success(self, string = 'OK'):
        if self.hasmsg and string:
            string = ': ' + string
        self.spinner.stop(text.bold_green('+'))
            self.stat.update(string)
        self.stat.freeze()
        self._remove()

    def failure(self, string = 'FAILED!'):
        if self.hasmsg and string:
            string = ': ' + string
        self.spinner.stop(text.bold_red('-'))
        self.stat.update(string)
        self.stat.freeze()
        self._remove()


def waitfor(msg, status = '', spinner = None, log_level = log_levels.INFO):
    """waitfor(msg, status = '', spinner = None) -> waiter

    Starts a new progress indicator which includes a spinner
    if :data:`pwnlib.term.term_mode` is enabled. By default it
    outputs to loglevel :data:`pwnlib.log_levels.INFO`.

    Args:
      msg (str): The message of the spinner.
      status (str): The initial status of the spinner.
      spinner (list): This should either be a list of strings or None.
         If a list is supplied, then a either element of the list
         is shown in order, with an update occuring every 0.1 second.
         Otherwise a random spinner is chosen.
      log_level(int): The log level to output the text to.

    Returns:
      A waiter-object that can be updated using :func:`status`, :func:`done_success` or :func:`done_failure`.
    """

    if context.log_level > log_level:
        h = _DummyWaiter()
    elif term.term_mode:
        h = _TermWaiter(msg, spinner, log_level)
    else:
        h = _SimpleWaiter(msg, spinner, log_level)

    if status:
        h.status(status)

    _waiter_stack.append(h)
    return h


def status(string = '', waiter = None):
    """Updates the status-text of waiter-object without completing it.

    Args:
      string (str): The status message.
      waiter: An optional waiter to update. If none is supplied, the last created one is used.
    """
    if waiter == None and _waiter_stack:
        waiter = _waiter_stack[-1]

    if waiter == None:
        raise Exception('Not waiting for anything')

    waiter.status(string)


def done_success(string = 'Done', waiter = None):
    """Updates the status-text of a waiter-object, and then sets it to completed in a successful manner.

    Args:
      string (str): The status message.
      waiter: An optional waiter to update. If none is supplied, the last created one is used.
    """
    if waiter == None and _waiter_stack:
        waiter = _waiter_stack[-1]

    if waiter == None:
        raise Exception('Not waiting for anything')

    waiter.success(string)


def done_failure(string = 'FAILED!', waiter = None):
    """Updates the status-text of a waiter-object, and then sets it to completed in a failed manner.

    Args:
      string (str): The status message.
      waiter: An optional waiter to update. If none is supplied, the last created one is used.
    """
    if waiter == None and _waiter_stack:
        waiter = _waiter_stack[-1]

    if waiter == None:
        raise Exception('Not waiting for anything')

    waiter.failure(string)
