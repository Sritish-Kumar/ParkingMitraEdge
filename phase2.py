"""
main.py — Phase 2 runner.

Capture -> queue -> analyzer -> state machine -> outbox -> MQTT.

The path an event takes:
    state machine confirms a change
        -> written to SQLite outbox (durable)
        -> relay thread publishes it when the broker is reachable
        -> marked sent only after the broker acknowledges

Kill the broker and events keep accumulating on disk. Bring it back and
they flush, in order, with no duplicates.

Run:  python main.py
Stop: Ctrl+C
"""

import os
import signal
import sys
import threading
import time
from datetime import datetime

from analyzers.fake import FakeAnalyzer
from edge.config import load_site
from edge.events import slot_state_changed, topic_for
from edge.frame_queue import FrameQueue
from edge.heartbeat import Heartbeat
from edge.outbox import Outbox
from edge.pipeline import Pipeline
from edge.publisher import Publisher
from edge.supervisor import Supervisor

BROKER_HOST = os.environ.get("MQTT_HOST", "localhost")
BROKER_PORT = int(os.environ.get("MQTT_PORT", "1883"))
STATS_EVERY = 10.0


def main():
    site = load_site("config/cameras.yaml")
    print(f"site={site.site_id}  cameras={len(site.cameras)}")

    analyzer = FakeAnalyzer()
    for cam in site.cameras.values():
        analyzer.configure(cam.camera_id, cam.slots)
        print(f"  {cam.camera_id}  {cam.sample_fps} fps  "
              f"slots={[s.slot_id for s in cam.slots]}")

    outbox = Outbox("outbox.db")
    publisher = Publisher(outbox, BROKER_HOST, BROKER_PORT,
                          client_id=f"edge-{site.site_id}")
    queue = FrameQueue(maxsize=32)
    supervisor = Supervisor(site.cameras, queue)

    def handle_event(e):
        calib = site.cameras[e.camera_id].calib_version
        payload = slot_state_changed(site.site_id, e, calib)
        outbox.add(topic_for(payload), payload)

        ts = datetime.fromtimestamp(e.observed_at).strftime("%H:%M:%S")
        flag = "  ***" if e.new_state == "BAD" else ""
        print(f"[{ts}] EVENT {e.camera_id} {e.slot_id} "
              f"{e.prev_state}->{e.new_state} {e.reason}{flag}  "
              f"id={payload['event_id'][:8]}")

    pipeline = Pipeline(site.cameras, analyzer, queue, on_event=handle_event)
    hb = Heartbeat(site, supervisor, pipeline, outbox)

    def shutdown(*_):
        print("\nstopping...")
        pipeline.stop(); hb.stop(); supervisor.stop(); publisher.stop()
        unsent, sent = outbox.counts()
        print(f"outbox: {unsent} unsent, {sent} sent")
        outbox.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)

    def stats_loop():
        while True:
            time.sleep(STATS_EVERY)
            unsent, sent = outbox.counts()
            link = "up" if publisher.connected else "DOWN"
            print(f"{supervisor.stats()} | analysed={pipeline.processed} "
                  f"| mqtt={link} published={publisher.published} "
                  f"| outbox unsent={unsent} sent={sent}")

    threading.Thread(target=stats_loop, daemon=True).start()

    print(f"\nbroker {BROKER_HOST}:{BROKER_PORT} - Ctrl+C to stop\n")
    publisher.start()
    supervisor.start()
    hb.start()
    pipeline.run()


if __name__ == "__main__":
    main()