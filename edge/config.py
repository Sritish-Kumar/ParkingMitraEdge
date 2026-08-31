"""
edge/config.py — reads the config files into typed Python objects.

The rest of the code never opens a file or parses YAML. It just asks
for cameras and gets objects back. If we later move config to a
database or a Config API, only this file changes.
"""

import json
from dataclasses import dataclass
from pathlib import Path

import yaml

from contracts import Slot


@dataclass(frozen=True)
class CameraConfig:
    camera_id: str
    source: str
    sample_fps: float
    slots: list[Slot]
    calib_version: str


def _load_slots(path: Path) -> tuple[list[Slot], str]:
    """Read one camera's slot file and turn each entry into a Slot object."""
    data = json.loads(path.read_text())

    slots = []
    for s in data["slots"]:
        slots.append(
            Slot(
                slot_id=s["slot_id"],
                polygon=[tuple(p) for p in s["polygon"]],
                center=tuple(s["center"]),
                angle=float(s["angle"]),
            )
        )
    return slots, data.get("calib_version", "v0")


def load_cameras(path: str = "config/cameras.yaml") -> dict[str, CameraConfig]:
    """
    Returns only the cameras marked enabled, keyed by camera_id.

    Skipping disabled cameras here means the rest of the system never
    has to check an 'enabled' flag anywhere.
    """
    root = Path(path).parent.parent
    data = yaml.safe_load(Path(path).read_text())

    cameras: dict[str, CameraConfig] = {}
    for c in data["cameras"]:
        if not c.get("enabled", True):
            continue

        slots, calib_version = _load_slots(root / c["slot_file"])
        cameras[c["camera_id"]] = CameraConfig(
            camera_id=c["camera_id"],
            source=c["source"],
            sample_fps=float(c["sample_fps"]),
            slots=slots,
            calib_version=calib_version,
        )

    if not cameras:
        raise RuntimeError(f"No enabled cameras found in {path}")

    return cameras