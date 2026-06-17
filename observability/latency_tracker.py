"""latency_tracker — đo latency (context manager)."""

from __future__ import annotations

import time


class Timer:
    def __enter__(self):
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, *exc):
        self.elapsed_ms = round((time.perf_counter() - self._t0) * 1000, 1)
        return False
