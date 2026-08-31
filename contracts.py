"""
contracts.py — the agreement between us and the model team.

Nothing in here does any work. It only defines SHAPES:
  - what a parking slot looks like
  - what a verdict about a slot looks like
  - what the model team's component must provide

Both our FakeAnalyzer and their real analyzer implement the same
Protocol, so our pipeline never knows which one it is talking to.
"""

from dataclasses import dataclass
from typing import Optional, Protocol

# Every reason string the analyzer is allowed to return.
# Keeping this list here means both sides agree on the vocabulary.
REASONS = (
    "EMPTY",                 # no vehicle in the slot
    "OK",                    # vehicle present and well parked
    "BOUNDARY_INTRUSION",    # sticking out over the line
    "ORIENTATION",           # parked crooked
    "DOUBLE_SLOT",           # taking up more than one slot
    "UNKNOWN",               # analyzer could not decide (occluded, blurry)
)


@dataclass(frozen=True)
class Slot:
    """One parking slot, as seen by ONE camera, in that camera's pixels."""
    slot_id: str                          # "A07" - unique across the whole site
    polygon: list[tuple[float, float]]    # corners, clockwise
    center: tuple[float, float]
    angle: float                          # degrees, slot's own orientation


@dataclass(frozen=True)
class SlotVerdict:
    """
    What the analyzer tells us about ONE slot in ONE frame.

    This is a snapshot, not a conclusion. It says what is true right now.
    Deciding whether it has been true long enough to act on is OUR job.
    """
    slot_id: str
    occupied: bool
    score: Optional[float]                # 0-100, None when the slot is empty
    reason: str                           # one of REASONS
    vehicle_type: Optional[str] = None    # "car" | "bus" | "truck" | "bike"
    bbox: Optional[tuple] = None          # x1, y1, x2, y2 - used for evidence crops


class Analyzer(Protocol):
    """
    The seam. Anything that satisfies this can be plugged into the pipeline.

    Rules the implementation must follow:

      1. configure() is called once per camera at startup.
      2. analyze() returns ONE verdict per slot, EVERY call,
         including slots that are empty.
      3. analyze() is stateless in TIME. Remembering polygons is fine.
         Remembering what happened in earlier frames is not - that is ours.
      4. Same frame in, same verdicts out. No randomness.
    """

    def configure(self, camera_id: str, slots: list[Slot]) -> None:
        ...

    def analyze(self, camera_id: str, frame) -> list[SlotVerdict]:
        ...