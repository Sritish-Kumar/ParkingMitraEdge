"""
main.py — Phase 1 runner.

Real capture threads, a bounded queue, a state machine, and confirmed
events printed to the terminal. No MQTT yet - that is Phase 2.

Run:  python main.py
"""

import signal
import sys
import threading
import time
from datetime import datetime

from analyzers.fake import FakeAnalyzer
from edge.config import load_cameras
from edge.frame_queue import FrameQueue
from edge.pipeline import Pipeline
from edge.supervisor import Supervisor

STATS_EVERY = 5.0


def print_event(e):
    ts = datetime.fromtimestamp(e.observed_at).strftime("%H:%M:%S")
    arrow = f"{e.prev_state} -> {e.new_state}"
    score = f"{e.score:.1f}" if e.score is not None else "-"
    flag = "  ***" if e.new_state == "BAD" else ""
    print(f"[{ts}] EVENT  {e.camera_id}  {e.slot_id}  {arrow:16s} "
          f"score={score:>5s}  {e.reason}{flag}")


def main():
    cameras = load_cameras("config/cameras.yaml")
    print(f"Loaded {len(cameras)} camera(s)")

    analyzer = FakeAnalyzer()
    for cam in cameras.values():
        analyzer.configure(cam.camera_id, cam.slots)
        print(f"  {cam.camera_id}  {cam.sample_fps} fps  "
              f"slots={[s.slot_id for s in cam.slots]}  src={cam.source}")

    queue = FrameQueue(maxsize=32)
    supervisor = Supervisor(cameras, queue)
    pipeline = Pipeline(cameras, analyzer, queue, on_event=print_event)

    def shutdown(*_):
        print("\nstopping...")
        pipeline.stop()
        supervisor.stop()
        print("final state:", pipeline.snapshot())
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)

    def stats_loop():
        while True:
            time.sleep(STATS_EVERY)
            print(f"{supervisor.stats()} | analysed={pipeline.processed}")

    threading.Thread(target=stats_loop, daemon=True).start()

    print("\nrunning - Ctrl+C to stop\n")
    supervisor.start()
    pipeline.run()


if __name__ == "__main__":
    main()