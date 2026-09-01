# """
# edge/capture.py — one thread per camera.

# Each worker owns exactly one video source and does three things:
#   1. keeps the connection alive (reconnects with backoff when it drops)
#   2. reads frames as fast as the source delivers them
#   3. pushes only `sample_fps` of them into the shared queue

# Point 2 and 3 are separate on purpose. We must keep calling read() to
# drain the camera's buffer, otherwise frames pile up inside OpenCV and
# we end up several seconds behind. But we only ANALYSE a few per second,
# so most of what we read is thrown away immediately.
# """

# import threading
# import time

# import cv2


# class CameraWorker(threading.Thread):
#     def __init__(self, cam, queue):
#         super().__init__(name=f"cap-{cam.camera_id}", daemon=True)
#         self.cam = cam
#         self.queue = queue
#         self._stop = threading.Event()

#         # health / stats, read by the supervisor
#         self.status = "STARTING"      # STARTING | ONLINE | OFFLINE
#         self.frames_read = 0
#         self.frames_queued = 0
#         self.reconnects = 0
#         self.last_frame_at = 0.0

#     def stop(self):
#         self._stop.set()

#     # ------------------------------------------------------------------ #

#     def run(self):
#         backoff = 1.0

#         while not self._stop.is_set():
#             cap = cv2.VideoCapture(self.cam.source)

#             if not cap.isOpened():
#                 self.status = "OFFLINE"
#                 self.reconnects += 1
#                 time.sleep(backoff)
#                 backoff = min(backoff * 2, 15.0)     # 1, 2, 4, 8, 15, 15...
#                 continue

#             self.status = "ONLINE"
#             backoff = 1.0
#             self._pump(cap)
#             cap.release()

#             if not self._stop.is_set():
#                 self.status = "OFFLINE"
#                 self.reconnects += 1
#                 time.sleep(1.0)

#     def _pump(self, cap):
#         """Read from an open capture until it fails or we are told to stop."""
#         interval = 1.0 / self.cam.sample_fps
#         next_put = 0.0

#         # A file plays back as fast as the CPU allows, which is not realistic.
#         # Pace it to its own frame rate so a demo behaves like a live camera.
#         is_file = "://" not in self.cam.source
#         src_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
#         frame_delay = 1.0 / src_fps if is_file else 0.0

#         while not self._stop.is_set():
#             ok, frame = cap.read()

#             if not ok:
#                 if is_file:                       # video ended - loop it
#                     cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
#                     continue
#                 return                            # stream died - reconnect

#             self.frames_read += 1
#             self.last_frame_at = time.time()

#             now = time.monotonic()
#             if now >= next_put:
#                 self.queue.put((self.cam.camera_id, time.time(), frame))
#                 self.frames_queued += 1
#                 next_put = now + interval

#             if frame_delay:
#                 time.sleep(frame_delay)

"""
edge/capture.py — one thread per camera.

Each worker owns exactly one video source and does three things:
  1. keeps the connection alive (reconnects with backoff when it drops)
  2. reads frames as fast as the source delivers them
  3. pushes only `sample_fps` of them into the shared queue

Point 2 and 3 are separate on purpose. We must keep calling read() to
drain the camera's buffer, otherwise frames pile up inside OpenCV and
we end up several seconds behind. But we only ANALYSE a few per second,
so most of what we read is thrown away immediately.
"""

import threading
import time

import cv2


class CameraWorker(threading.Thread):
    def __init__(self, cam, queue):
        super().__init__(name=f"cap-{cam.camera_id}", daemon=True)
        self.cam = cam
        self.queue = queue
        self._shutdown = threading.Event()

        # health / stats, read by the supervisor
        self.status = "STARTING"      # STARTING | ONLINE | OFFLINE
        self.frames_read = 0
        self.frames_queued = 0
        self.reconnects = 0
        self.last_frame_at = 0.0

    def stop(self):
        self._shutdown.set()

    # ------------------------------------------------------------------ #

    def run(self):
        backoff = 1.0

        while not self._shutdown.is_set():
            cap = cv2.VideoCapture(self.cam.source)

            if not cap.isOpened():
                self.status = "OFFLINE"
                self.reconnects += 1
                time.sleep(backoff)
                backoff = min(backoff * 2, 15.0)     # 1, 2, 4, 8, 15, 15...
                continue

            self.status = "ONLINE"
            backoff = 1.0
            self._pump(cap)
            cap.release()

            if not self._shutdown.is_set():
                self.status = "OFFLINE"
                self.reconnects += 1
                time.sleep(1.0)

    def _pump(self, cap):
        """Read from an open capture until it fails or we are told to stop."""
        interval = 1.0 / self.cam.sample_fps
        next_put = 0.0

        # A file plays back as fast as the CPU allows, which is not realistic.
        # Pace it to its own frame rate so a demo behaves like a live camera.
        is_file = "://" not in self.cam.source
        src_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        frame_delay = 1.0 / src_fps if is_file else 0.0

        while not self._shutdown.is_set():
            ok, frame = cap.read()

            if not ok:
                if is_file:                       # video ended - loop it
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                return                            # stream died - reconnect

            self.frames_read += 1
            self.last_frame_at = time.time()

            now = time.monotonic()
            if now >= next_put:
                self.queue.put((self.cam.camera_id, time.time(), frame))
                self.frames_queued += 1
                next_put = now + interval

            if frame_delay:
                time.sleep(frame_delay)