"""
tools/subscribe.py — stand in for the cloud.

This is what the browser will do later, and a simplified version of what
the real Ingest service will do in Phase 3:

    connect to the broker
    subscribe to everything
    branch on event_type
    reject event_ids we have already seen

Usage:
    python tools/subscribe.py                 pretty output
    python tools/subscribe.py --raw           dump the JSON exactly as sent
    python tools/subscribe.py --host 1.2.3.4  another broker

Stop with Ctrl+C. It prints a summary of what it received.
"""

import argparse
import json
import uuid
from collections import Counter
from datetime import datetime

import paho.mqtt.client as mqtt

COLOUR = {"EMPTY": "\033[90m", "OK": "\033[92m", "BAD": "\033[91m"}
RESET = "\033[0m"
SYMBOL = {"EMPTY": ".", "OK": "O", "BAD": "X"}

seen_ids: set[str] = set()
counts = Counter()


def short_time(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%H:%M:%S")
    except Exception:
        return iso[:8]


def show_heartbeat(m: dict) -> None:
    slots = m["slots"]
    tally = Counter(slots.values())

    print(f"\n[{short_time(m['emitted_at'])}] HEARTBEAT  {m['camera_id']}  "
          f"status={m['camera_status']}  calib={m['calib_version']}")
    print(f"           EMPTY={tally.get('EMPTY', 0)}  "
          f"OK={tally.get('OK', 0)}  BAD={tally.get('BAD', 0)}")

    # slot map, 8 per row
    line = "           "
    for i, (slot_id, state) in enumerate(sorted(slots.items())):
        if i and i % 8 == 0:
            print(line)
            line = "           "
        line += (f"{COLOUR.get(state, '')}{slot_id}:"
                 f"{SYMBOL.get(state, '?')}{RESET}  ")
    print(line)


def show_event(m: dict) -> None:
    colour = COLOUR.get(m["new_state"], "")
    score = f"{m['score']:.1f}" if m.get("score") is not None else "  -"
    lag = ""
    try:
        gap = (datetime.fromisoformat(m["emitted_at"])
               - datetime.fromisoformat(m["observed_at"])).total_seconds()
        if gap > 2.0:
            lag = f"   <-- REPLAYED after {gap:.0f}s buffered"
    except Exception:
        pass

    print(f"\n[{short_time(m['observed_at'])}] {colour}EVENT      "
          f"{m['camera_id']}  {m['slot_id']}  "
          f"{m['prev_state']} -> {m['new_state']}{RESET}  "
          f"score={score}  {m['reason']}  id={m['event_id'][:8]}{lag}")


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("connected - waiting for messages (Ctrl+C to stop)\n")
        client.subscribe("pm/#", qos=1)
    else:
        print(f"connect failed: {reason_code}")


def on_message(client, userdata, msg):
    raw = msg.payload.decode()

    if userdata["raw"]:
        print(f"{msg.topic}  {raw}")
        return

    try:
        m = json.loads(raw)
    except json.JSONDecodeError:
        print(f"!! bad JSON on {msg.topic}")
        counts["malformed"] += 1
        return

    event_id = m.get("event_id")
    if event_id in seen_ids:
        # This is exactly what Ingest will do with a UNIQUE constraint.
        print(f"   DUPLICATE ignored  id={event_id[:8]}")
        counts["duplicate"] += 1
        return
    seen_ids.add(event_id)

    kind = m.get("event_type")
    counts[kind] += 1

    if kind == "HEARTBEAT":
        show_heartbeat(m)
    elif kind == "SLOT_STATE_CHANGED":
        show_event(m)
    else:
        print(f"   unknown event_type: {kind}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--client-id", default=None,
                    help="MQTT client id; defaults to a unique subscriber id")
    ap.add_argument("--raw", action="store_true", help="print JSON as received")
    args = ap.parse_args()

    client_id = args.client_id or f"subscriber-demo-{uuid.uuid4().hex[:8]}"
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         client_id=client_id,
                         userdata={"raw": args.raw})
    client.on_connect = on_connect
    client.on_message = on_message

    print(f"connecting to {args.host}:{args.port} as {client_id} ...")
    client.connect(args.host, args.port, keepalive=60)

    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print("\n\n--- summary ---")
        for k, v in counts.items():
            print(f"  {k:20s} {v}")
        print(f"  unique event_ids     {len(seen_ids)}")
        client.disconnect()


if __name__ == "__main__":
    main()
