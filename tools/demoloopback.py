"""
tools/demo_loopback.py — run the edge and a subscriber in one process.

Handy for checking the transport end to end without juggling terminals.
For the real demo, run main.py and tools/subscribe.py separately.

    python tools/demo_loopback.py 25      # run for 25 seconds
"""

import sys
import threading
import time
from pathlib import Path

import paho.mqtt.client as mqtt

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tools.subscribe as sub
from analyzers.fake import FakeAnalyzer
from edge.config import load_site
from edge.events import slot_state_changed, topic_for
from edge.frame_queue import FrameQueue
from edge.heartbeat import Heartbeat
from edge.outbox import Outbox
from edge.pipeline import Pipeline
from edge.publisher import Publisher
from edge.supervisor import Supervisor

SECONDS = int(sys.argv[1]) if len(sys.argv) > 1 else 25


def main():
    # the "cloud" side
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                    client_id="sub-demo",
                    userdata={"raw": False})
    c.on_connect = sub.on_connect
    c.on_message = sub.on_message
    c.connect("localhost", 1883, 60)
    c.loop_start()
    time.sleep(1)

    # the edge side
    site = load_site("config/cameras.yaml")
    analyzer = FakeAnalyzer()
    for cam in site.cameras.values():
        analyzer.configure(cam.camera_id, cam.slots)

    outbox = Outbox("outbox.db")
    publisher = Publisher(outbox, "localhost", 1883,
                          client_id="edge-demo", on_log=lambda m: None)
    queue = FrameQueue(32)
    supervisor = Supervisor(site.cameras, queue)

    def on_ev(e):
        payload = slot_state_changed(
            site.site_id, e, site.cameras[e.camera_id].calib_version)
        outbox.add(topic_for(payload), payload)

    pipeline = Pipeline(site.cameras, analyzer, queue, on_event=on_ev)
    hb = Heartbeat(site, supervisor, pipeline, outbox)

    publisher.start()
    supervisor.start()
    hb.start()
    threading.Thread(target=pipeline.run, daemon=True).start()

    time.sleep(SECONDS)

    pipeline.stop(); hb.stop(); supervisor.stop(); publisher.stop()
    c.loop_stop()

    print("\n--- summary ---")
    for k, v in sub.counts.items():
        print(f"  {k:20s} {v}")
    print(f"  unique event_ids     {len(sub.seen_ids)}")
    print(f"  outbox unsent/sent   {outbox.counts()}")


if __name__ == "__main__":
    main()
