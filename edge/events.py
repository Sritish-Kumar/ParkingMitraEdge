"""
edge/events.py — the wire format.

Everything the edge sends to the cloud is built here, so there is exactly
one place that defines what an event looks like. The central Ingest
service validates against this same shape.

Two event types:

  SLOT_STATE_CHANGED  a confirmed transition. Rare - only on change.
  HEARTBEAT           full snapshot of a camera's slots, every 30s.

Why both? Events are fast but can be lost. The heartbeat is the
correction: if an event ever goes missing, central state repairs itself
within 30 seconds instead of staying wrong forever.
"""

import uuid
from datetime import datetime, timezone


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds")


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).astimezone().isoformat(
        timespec="milliseconds"
    )


def slot_state_changed(site_id: str, event, calib_version: str) -> dict:
    """Build the payload for one confirmed SlotEvent."""
    return {
        "event_id": str(uuid.uuid4()),        # the idempotency key
        "event_type": "SLOT_STATE_CHANGED",
        "site_id": site_id,
        "camera_id": event.camera_id,
        "slot_id": event.slot_id,
        "prev_state": event.prev_state,
        "new_state": event.new_state,
        "score": event.score,
        "reason": event.reason,
        "vehicle_type": event.vehicle_type,
        "bbox": list(event.bbox) if event.bbox else None,
        "calib_version": calib_version,       # which polygons produced this
        "observed_at": _iso(event.observed_at),   # when it happened
        "emitted_at": _now_iso(),                 # when we built the message
    }


def heartbeat(site_id: str, camera_id: str, status: str,
              slots: dict, calib_version: str) -> dict:
    """Full current state of one camera's slots."""
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": "HEARTBEAT",
        "site_id": site_id,
        "camera_id": camera_id,
        "camera_status": status,              # ONLINE | OFFLINE | STALE
        "slots": slots,                       # {"A07": "OK", "A08": "BAD"}
        "calib_version": calib_version,
        "emitted_at": _now_iso(),
    }


def topic_for(payload: dict) -> str:
    kind = "heartbeat" if payload["event_type"] == "HEARTBEAT" else "events"
    return f"pm/{payload['site_id']}/{payload['camera_id']}/{kind}"