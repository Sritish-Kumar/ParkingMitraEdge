"""
edge/frame_queue.py — the buffer between cameras and the pipeline.

The important behaviour is DROP-OLDEST.

If the analyzer falls behind, we must throw frames away. The alternative
(letting the queue grow) means we would slowly start analysing older and
older footage while memory climbs - the system looks alive but is
reporting the past. Dropping keeps latency bounded.

A deque with maxlen does this for free: appending to a full deque
silently discards the item at the other end.
"""

import threading
from collections import deque


class FrameQueue:
    def __init__(self, maxsize: int = 32):
        self._dq = deque(maxlen=maxsize)
        self._cond = threading.Condition()
        self.dropped = 0          # how many frames we threw away
        self.accepted = 0         # how many made it in

    def put(self, item) -> None:
        """Never blocks. Never fails. May silently drop the oldest frame."""
        with self._cond:
            if len(self._dq) == self._dq.maxlen:
                self.dropped += 1
            self._dq.append(item)
            self.accepted += 1
            self._cond.notify()

    def get(self, timeout: float = 0.5):
        """Returns the oldest frame, or None if nothing arrived in `timeout`."""
        with self._cond:
            if not self._dq:
                self._cond.wait(timeout)
            if not self._dq:
                return None
            return self._dq.popleft()

    def depth(self) -> int:
        with self._cond:
            return len(self._dq)