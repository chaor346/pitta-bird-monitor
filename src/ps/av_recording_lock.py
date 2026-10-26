"""Linux flock: held only while visual recording/conversion is active.
Do not delete/replace the lock file while either program is running.
"""
import fcntl
import os
import time

class RecordingLock:
    def __init__(self, path):
        self.path = os.path.abspath(path)
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o666)
        self.held = False

    def _stamp(self):
        os.lseek(self.fd, 0, os.SEEK_SET)
        os.write(self.fd, ('%d %d\n' % (os.getpid(), int(time.time()*1000000))).encode('ascii'))
        os.ftruncate(self.fd, os.lseek(self.fd, 0, os.SEEK_CUR))

    def begin(self):
        if self.held:
            return
        fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.held = True
        self._stamp()

    def end(self):
        if self.held:
            try:
                self._stamp()
            finally:
                fcntl.flock(self.fd, fcntl.LOCK_UN)
                self.held = False

    def close(self):
        self.end()
        os.close(self.fd)


def recording_state(path):
    """Return (busy, generation). Process exit automatically releases flock."""
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o666)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            return True, os.fstat(fd).st_mtime_ns
        try:
            return False, os.fstat(fd).st_mtime_ns
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)
