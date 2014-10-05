#!/usr/bin/env python2
from pwn import *
from collections import defaultdict

# data = wget('http://www.gutenberg.org/cache/epub/1952/pg1952.txt')

# print len(data)

class Test(tube.tube):
    def __init__(self, data, *args, **kwargs):
        self.__data = data
        print args
        super(Test, self).__init__(*args, **kwargs)
        self.pos = 0
        self.count = defaultdict(lambda:0)

    def recv_raw(self, nub):
        print 'recv_raw'
        self.count['recv_raw'] += 1
        rv = self.__data[self.pos:self.pos+nub]
        self.pos += nub
        return rv

    def send_raw(self, *args):
        pass
    def settimeout_raw(self, timeout):  return True
    def can_recv_raw(self, timeout):    return True
    def connected_raw(self, direction): return True
    def close(self):                    return True
    def shutdown_raw(self, direction):  return True


# print len(t.recv())
# assert len(t.recv()) == 4096


class SingleTube(tube.tube):
    def __init__(self, *args, **kwargs):
        super(SingleTube, self).__init__(*args, **kwargs)
        self.i = 0
    def recv_raw(self, nub):
        if self.i < 100:
            rv = 'a'
        else:
            rv = 'a\n' * 100
        self.i += 1
        return rv


t = SingleTube('default')
assert len(t.recvline()) == 100