"""
analyzers/fake.py — a stand-in for the model team's component.

It ignores the image completely and replays a SCRIPTED timeline:
every run produces the exact same sequence of slot states. That makes
the whole pipeline testable and the demo repeatable.

When the real analyzer arrives, we delete nothing here - we just point
main.py at the real one instead.
"""

from contracts import Slot, SlotVerdict

# The script. For each slot, a list of:
#     (from_frame, occupied, score, reason)
#
# The pipeline runs at ~5 fps, so frame 60 is roughly 12 seconds in.
# Edit these numbers to test different scenarios.
SCRIPT: dict[str, list[tuple]] = {
    "A07": [
        (0, True, 93.0, "OK"),                       # parked well the whole time
    ],
    "A08": [
        (0, False, None, "EMPTY"),                   # slot is free
        (30, True, 78.0, "OK"),                      # a car arrives
        (60, True, 47.5, "BOUNDARY_INTRUSION"),      # it drifts over the line
        (200, True, 88.0, "OK"),                     # driver corrects it
    ],
    "A09": [
        (0, False, None, "EMPTY"),                   # never used
    ],
    "B01": [
        (0, True, 91.0, "OK"),
    ],
    "B02": [
        (0, False, None, "EMPTY"),
        (40, True, 38.0, "ORIENTATION"),             # arrives already crooked
    ],
    "C01": [
        (0, False, None, "EMPTY"),
    ],
    "C02": [
        (0, True, 85.0, "OK"),
    ],
}

# Fake bounding boxes, so evidence-crop code has something to work with later.
BOXES = {
    "A07": (620, 702, 938, 886),
    "A08": (591, 598, 880, 728),
    "A09": None,
}


# Used for any slot not named in SCRIPT, so the fake works with whatever
# slot ids your calibration produced. Slot #0 stays OK, slot #1 goes bad,
# slot #2 fills up late, the rest stay empty.
DEFAULT_TIMELINES = [
    [(0, True, 93.0, "OK")],
    [(0, False, None, "EMPTY"),
     (30, True, 78.0, "OK"),
     (60, True, 47.5, "BOUNDARY_INTRUSION"),
     (400, True, 88.0, "OK")],
    [(0, False, None, "EMPTY"),
     (90, True, 41.0, "ORIENTATION")],
    [(0, False, None, "EMPTY")],
]


def _state_at(timeline: list[tuple], frame: int) -> tuple:
    """Pick the last scripted entry whose start frame has been reached."""
    current = timeline[0]
    for entry in timeline:
        if frame >= entry[0]:
            current = entry
        else:
            break
    return current


class FakeAnalyzer:
    """Implements the Analyzer protocol from contracts.py."""

    def __init__(self):
        self._slots: dict[str, list[Slot]] = {}
        self._frame_no: dict[str, int] = {}

    def configure(self, camera_id: str, slots: list[Slot]) -> None:
        """Called once at startup. The real analyzer would store polygons here."""
        self._slots[camera_id] = slots
        self._frame_no[camera_id] = 0

    def analyze(self, camera_id: str, frame) -> list[SlotVerdict]:
        if camera_id not in self._slots:
            raise RuntimeError(f"configure() was never called for {camera_id}")

        self._frame_no[camera_id] += 1
        n = self._frame_no[camera_id]

        verdicts = []
        for i, slot in enumerate(self._slots[camera_id]):
            timeline = SCRIPT.get(
                slot.slot_id,
                DEFAULT_TIMELINES[i % len(DEFAULT_TIMELINES)],
            )
            if timeline is None:
                timeline = DEFAULT_TIMELINES[i % len(DEFAULT_TIMELINES)]
            _, occupied, score, reason = _state_at(timeline, n)

            verdicts.append(
                SlotVerdict(
                    slot_id=slot.slot_id,
                    occupied=occupied,
                    score=score,
                    reason=reason,
                    vehicle_type="car" if occupied else None,
                    bbox=BOXES.get(slot.slot_id) if occupied else None,
                )
            )
        return verdicts