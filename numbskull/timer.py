"""TODO."""

import time


class Timer:
    """TODO."""

    def __enter__(self):
        """TODO."""
        self.start = time.time()
        return self

    def __exit__(self, *args):
        """TODO."""
        self.end = time.time()
        self.interval = self.end - self.start
