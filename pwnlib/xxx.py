

class Foo(object):
    @property
    def foo(self):
        return self._foo
    @foo.setter
    def foo(self, value):
        self._foo = value
    def __init__(self):
        self.foo = 'abcdef'