"""
edge/publisher.py — gets events out of the outbox and onto the broker.

The pipeline never talks to MQTT. It writes to the outbox and moves on.
A separate relay thread drains the outbox whenever the broker is
reachable. That separation is why a dead network cannot slow down or
crash the analysis loop.

qos=1 means "at least once": the broker acknowledges every message, and
paho re-sends anything unacknowledged. It can deliver twice, which is
fine - the central side rejects duplicate event_ids.
"""

import json
import threading
import time

import paho.mqtt.client as mqtt

PUBLISH_TIMEOUT = 5.0
IDLE_SLEEP = 0.5


class Publisher:
    def __init__(self, outbox, host: str = "localhost", port: int = 1883,
                 client_id: str = "edge", on_log=print):
        self.outbox = outbox
        self.host = host
        self.port = port
        self.on_log = on_log
        self.connected = False
        self.published = 0

        self._stop = threading.Event()
        self._client = mqtt.Client(client_id=client_id)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect

    # ---------------------------------------------------------------- #

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        self.connected = reason_code == 0
        self.on_log(f"[mqtt] connected ({reason_code})" if self.connected
                    else f"[mqtt] connect refused ({reason_code})")

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        self.connected = False
        self.on_log("[mqtt] disconnected - events will buffer locally")

    # ---------------------------------------------------------------- #

    def start(self) -> None:
        try:
            self._client.connect_async(self.host, self.port, keepalive=60)
        except Exception as exc:
            self.on_log(f"[mqtt] {exc}")

        # loop_start runs paho's own background thread: it reconnects on
        # its own, so we never write retry logic ourselves.
        self._client.loop_start()
        threading.Thread(target=self._relay, name="relay", daemon=True).start()

    def stop(self) -> None:
        self._stop.set()
        self._client.loop_stop()
        self._client.disconnect()

    def _relay(self) -> None:
        while not self._stop.is_set():
            if not self.connected:
                time.sleep(1.0)
                continue

            rows = self.outbox.pending(limit=50)
            if not rows:
                time.sleep(IDLE_SLEEP)
                continue

            for event_id, topic, payload in rows:
                if self._stop.is_set():
                    return
                if not self._send(event_id, topic, payload):
                    break            # broker went away - retry on next pass

    def _send(self, event_id: str, topic: str, payload: str) -> bool:
        try:
            info = self._client.publish(topic, payload, qos=1)
            info.wait_for_publish(timeout=PUBLISH_TIMEOUT)
        except (ValueError, RuntimeError):
            return False

        if not info.is_published():
            return False

        self.outbox.mark_sent(event_id)
        self.published += 1
        return True