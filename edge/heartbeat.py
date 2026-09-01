# """
# edge/heartbeat.py — periodic full-state snapshot.

# Events only fire on change, which is efficient but fragile: if one is
# ever lost, central state stays wrong indefinitely. The heartbeat fixes
# that by resending the whole truth on a fixed interval.

# It also carries camera health. A camera that stops sending heartbeats
# is presumed blind, and its slots must be treated as unknown - never as
# free.
# """

# import threading
# import time

# from edge.events import heartbeat, topic_for

# INTERVAL_SECONDS = 30.0


# class Heartbeat(threading.Thread):
#     def __init__(self, site, supervisor, pipeline, outbox,
#                  interval: float = INTERVAL_SECONDS):
#         super().__init__(name="heartbeat", daemon=True)
#         self.site = site
#         self.supervisor = supervisor
#         self.pipeline = pipeline
#         self.outbox = outbox
#         self.interval = interval
#         self._stop = threading.Event()
#         self.sent = 0

#     def stop(self):
#         self._stop.set()

#     def run(self):
#         while not self._stop.wait(self.interval):
#             snapshot = self.pipeline.snapshot()

#             for camera_id, cam in self.site.cameras.items():
#                 payload = heartbeat(
#                     site_id=self.site.site_id,
#                     camera_id=camera_id,
#                     status=self.supervisor.health(camera_id),
#                     slots=snapshot.get(camera_id, {}),
#                     calib_version=cam.calib_version,
#                 )
#                 self.outbox.add(topic_for(payload), payload)
#                 self.sent += 1


"""
edge/heartbeat.py — periodic full-state snapshot.

Events only fire on change, which is efficient but fragile: if one is
ever lost, central state stays wrong indefinitely. The heartbeat fixes
that by resending the whole truth on a fixed interval.

It also carries camera health. A camera that stops sending heartbeats
is presumed blind, and its slots must be treated as unknown - never as
free.
"""

import threading
import time

from edge.events import heartbeat, topic_for

INTERVAL_SECONDS = 5.0


class Heartbeat(threading.Thread):
    def __init__(self, site, supervisor, pipeline, outbox,
                 interval: float = INTERVAL_SECONDS):
        super().__init__(name="heartbeat", daemon=True)
        self.site = site
        self.supervisor = supervisor
        self.pipeline = pipeline
        self.outbox = outbox
        self.interval = interval
        self._shutdown = threading.Event()
        self.sent = 0

    def stop(self):
        self._shutdown.set()

    def run(self):
        while not self._shutdown.wait(self.interval):
            snapshot = self.pipeline.snapshot()

            for camera_id, cam in self.site.cameras.items():
                payload = heartbeat(
                    site_id=self.site.site_id,
                    camera_id=camera_id,
                    status=self.supervisor.health(camera_id),
                    slots=snapshot.get(camera_id, {}),
                    calib_version=cam.calib_version,
                )
                self.outbox.add(topic_for(payload), payload)
                self.sent += 1