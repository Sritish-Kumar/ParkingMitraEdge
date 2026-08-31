"""
edge/pipeline.py — the consumer loop.

One loop, one thread. It pulls whatever frame is next in the queue,
regardless of which camera it came from, and routes it by camera_id.

Everything before this point is concurrent (many camera threads).
Everything from here on is sequential, which keeps the state machines
free of locks.
"""

import time

from edge.state_machine import SlotStateMachine


class Pipeline:
    def __init__(self, cameras: dict, analyzer, queue, on_event):
        self.analyzer = analyzer
        self.queue = queue
        self.on_event = on_event
        self.machines = {
            cam_id: SlotStateMachine(cam_id, [s.slot_id for s in cam.slots])
            for cam_id, cam in cameras.items()
        }
        self.processed = 0
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        while not self._stop:
            item = self.queue.get(timeout=0.5)
            if item is None:
                continue

            camera_id, captured_at, frame = item

            verdicts = self.analyzer.analyze(camera_id, frame)
            events = self.machines[camera_id].update(verdicts, now=captured_at)

            self.processed += 1
            for e in events:
                self.on_event(e)

    def snapshot(self) -> dict:
        """Confirmed state of every slot on every camera."""
        return {cam: m.snapshot() for cam, m in self.machines.items()}