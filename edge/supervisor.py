"""
edge/supervisor.py — owns the camera workers.

The workers reconnect on their own, so the supervisor's job is mostly
lifecycle (start/stop) and health reporting.

The health rule that matters: if a camera has not produced a frame
recently we call it STALE. Downstream, a STALE camera's slots must be
reported as unknown - NEVER as free. Inventing availability is worse
than admitting we cannot see.
"""

import time

from edge.capture import CameraWorker

STALE_AFTER_SECONDS = 10.0


class Supervisor:
    def __init__(self, cameras: dict, queue):
        self.queue = queue
        self.workers = {
            cam_id: CameraWorker(cam, queue) for cam_id, cam in cameras.items()
        }

    def start(self):
        for w in self.workers.values():
            w.start()

    def stop(self):
        for w in self.workers.values():
            w.stop()
        for w in self.workers.values():
            w.join(timeout=2.0)

    def health(self, camera_id: str) -> str:
        w = self.workers[camera_id]
        if w.status != "ONLINE":
            return w.status
        if time.time() - w.last_frame_at > STALE_AFTER_SECONDS:
            return "STALE"
        return "ONLINE"

    def stats(self) -> str:
        """One-line summary, printed periodically so the demo is observable."""
        parts = []
        for cam_id, w in self.workers.items():
            parts.append(
                f"{cam_id}:{self.health(cam_id)[:4]} "
                f"read={w.frames_read} q={w.frames_queued} rc={w.reconnects}"
            )
        return (f"[stats] depth={self.queue.depth()} "
                f"dropped={self.queue.dropped} | " + " | ".join(parts))