import os
import sys


class Logs:
    def __init__(self, fp=None, out=sys.stderr):
        """Create a logs instance on a logs file."""

        self.fp = None
        self.out = out
        if fp:
            if not os.path.isdir(os.path.dirname(fp)):
                os.makedirs(os.path.dirname(fp), exist_ok=True)
            self.fp = open(fp, mode="a")

    def info(self, msg):
        """Log a new message to the opened logs file, and optionally on stdout or stderr too."""
        if self.fp:
            self.fp.write(msg + os.linesep)
            self.fp.flush()

        if self.out:
            print(msg, file=self.out)

    def vinfo(self, some_str, some_var):
        assert type(some_str) is str
        self.info(some_str + ": " + str(some_var))

    @staticmethod
    def sinfo(msg):
        print(msg, file=sys.stderr, flush=True)

    @classmethod
    def svinfo(cls, some_str, some_var):
        assert type(some_str) is str
        cls.sinfo(some_str + ": " + str(some_var))
