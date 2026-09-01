"""
edge/state_machine.py — turns a stream of per-frame verdicts into events.

The analyzer answers "what is true in THIS frame".
This file answers "what is true, and has been for long enough to act on".

That gap is the whole reason the system is trustworthy. A car reversing
into a bay will look badly parked for a few seconds. A reflection can
make one frame look wrong. Neither should notify anyone.

We keep three confirmed states per slot:

    EMPTY  - no vehicle
    OK     - vehicle, parked acceptably
    BAD    - vehicle, not parked acceptably

A change is only committed once the new state has been observed
continuously for a configured number of seconds. Different transitions
get different patience: a car arriving is obvious, a violation is not.
"""

from dataclasses import dataclass
from typing import Optional

# How long a new state must hold before we believe it.
CONFIRM_SECONDS = {
    "EMPTY": 3.0,     # car left - fairly obvious
    "OK": 5.0,        # parked well / corrected
    "BAD": 5.0       # violation - be slow and sure
}

BAD_SCORE_BELOW = 50.0


@dataclass(frozen=True)
class SlotEvent:
    camera_id: str
    slot_id: str
    prev_state: str
    new_state: str
    score: Optional[float]
    reason: str
    vehicle_type: Optional[str]
    bbox: Optional[tuple]
    observed_at: float          # unix seconds


def _observed_state(v) -> Optional[str]:
    """Collapse a verdict into EMPTY / OK / BAD, or None to ignore it."""
    if v.reason == "UNKNOWN":
        return None                       # occluded or unsure - don't count it
    if not v.occupied:
        return "EMPTY"
    if v.reason == "OK" and (v.score is None or v.score >= BAD_SCORE_BELOW):
        return "OK"
    return "BAD"


class SlotStateMachine:
    """One instance per camera. Holds the state of all that camera's slots."""

    def __init__(self, camera_id: str, slot_ids: list[str]):
        self.camera_id = camera_id
        self.confirmed = {s: "EMPTY" for s in slot_ids}
        self._candidate: dict[str, Optional[str]] = {s: None for s in slot_ids}
        self._since: dict[str, float] = {s: 0.0 for s in slot_ids}

    def update(self, verdicts, now: float) -> list[SlotEvent]:
        """Feed one frame's verdicts. Returns only CONFIRMED changes."""
        events: list[SlotEvent] = []

        for v in verdicts:
            slot = v.slot_id
            if slot not in self.confirmed:
                continue

            observed = _observed_state(v)
            if observed is None:
                continue

            if observed == self.confirmed[slot]:
                self._candidate[slot] = None          # nothing changing
                continue

            if self._candidate[slot] != observed:     # a new candidate appeared
                self._candidate[slot] = observed
                self._since[slot] = now
                continue

            held_for = now - self._since[slot]
            if held_for < CONFIRM_SECONDS.get(observed, 10.0):
                continue                              # not convinced yet

            prev = self.confirmed[slot]               # commit the change
            self.confirmed[slot] = observed
            self._candidate[slot] = None

            events.append(SlotEvent(
                camera_id=self.camera_id,
                slot_id=slot,
                prev_state=prev,
                new_state=observed,
                score=v.score,
                reason=v.reason,
                vehicle_type=v.vehicle_type,
                bbox=v.bbox,
                observed_at=now,
            ))

        return events

    def snapshot(self) -> dict:
        """Current confirmed state of every slot - used for heartbeats later."""
        return dict(self.confirmed)