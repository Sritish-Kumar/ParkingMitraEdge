"""
analyzers/real.py — the model team's component, for real.

Runs a YOLO detector on the frame to find vehicle boxes, then checks
each configured slot polygon against the detections: how much of the
slot a vehicle covers, and how much of the vehicle sits inside the
slot. That coverage/containment pair is the whole "alignment check" -
simple by design, because an axis-aligned detector box carries no
rotation info, so a real ORIENTATION check needs an oriented-box model
later (yolov8n-obb.pt or similar). For now this analyzer only ever
emits EMPTY / OK / BOUNDARY_INTRUSION / DOUBLE_SLOT.

The thresholds below are deliberately loose - a real photographed
slot is a perspective-skewed quad, but the detector's box is always
an upright rectangle around the whole vehicle, so box vs. polygon
never overlaps as cleanly as two same-shaped regions would. Demanding
near-total overlap made almost everything look like a boundary
violation. Tighten these once real footage shows what "well parked"
actually measures like.

Implements the same Analyzer protocol as analyzers/fake.py - see
contracts.py. In particular it stays stateless in time: no memory of
earlier frames. Deciding whether a change has held long enough is
edge/state_machine.py's job, not this file's.
"""

import cv2
import numpy as np
from ultralytics import YOLO

from contracts import Slot, SlotVerdict

# COCO class id -> the vehicle_type vocabulary from contracts.py
VEHICLE_CLASSES = {2: "car", 3: "bike", 5: "bus", 7: "truck"}

MIN_COVERAGE = 0.30        # below this fraction of slot-area overlapped, the slot counts as EMPTY
FULL_COVERAGE = 0.55       # at/above this fraction of slot-area covered, the vehicle is "in" the slot
MIN_CONTAINMENT = 0.35     # below this fraction of the vehicle box inside the slot, it's not really parked there


class RealAnalyzer:
    """Implements the Analyzer protocol from contracts.py."""

    def __init__(self, weights_path="yolov8n.pt", conf=0.35, iou=0.45, device="cpu"):
        self.model = YOLO(weights_path)
        self.conf = conf
        self.iou = iou
        self.device = device

        self._slots: dict[str, list[Slot]] = {}
        self._polygons: dict[str, list[np.ndarray]] = {}
        self._areas: dict[str, list[float]] = {}

    def configure(self, camera_id: str, slots: list[Slot]) -> None:
        """Called once at startup. Normalizes each slot's polygon and caches its area."""
        self._slots[camera_id] = slots

        polygons, areas = [], []
        for slot in slots:
            pts = np.array(slot.polygon, dtype=np.float32)
            hull = cv2.convexHull(pts).reshape(-1, 2)   # clicked corners aren't guaranteed convex/clockwise
            polygons.append(hull)
            areas.append(cv2.contourArea(hull))

        self._polygons[camera_id] = polygons
        self._areas[camera_id] = areas

    def analyze(self, camera_id: str, frame) -> list[SlotVerdict]:
        if camera_id not in self._slots:
            raise RuntimeError(f"configure() was never called for {camera_id}")

        slots = self._slots[camera_id]
        polygons = self._polygons[camera_id]
        areas = self._areas[camera_id]

        detections = self._detect(frame)
        best, claims = self._match(polygons, areas, detections)

        verdicts = []
        for i, slot in enumerate(slots):
            match = best[i]
            if match is None:
                verdicts.append(SlotVerdict(
                    slot_id=slot.slot_id, occupied=False, score=None, reason="EMPTY",
                ))
                continue

            coverage, det_index, inter_area, box_area = match
            _, vehicle_type, xyxy = detections[det_index]

            verdicts.append(SlotVerdict(
                slot_id=slot.slot_id,
                occupied=True,
                score=round(min(coverage, 1.0) * 100, 1),
                reason=self._reason(coverage, inter_area, box_area, len(claims[det_index])),
                vehicle_type=vehicle_type,
                bbox=tuple(round(v) for v in xyxy),
            ))
        return verdicts

    # ------------------------------------------------------------------ #

    def _detect(self, frame) -> list[tuple]:
        """Run the model. Returns (box_polygon, vehicle_type, xyxy) per detection."""
        results = self.model.predict(
            frame,
            classes=list(VEHICLE_CLASSES),
            conf=self.conf,
            iou=self.iou,
            device=self.device,
            verbose=False,
        )[0]

        detections = []
        for box in results.boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            cls_id = int(box.cls[0])
            box_poly = np.array(
                [[x1, y1], [x2, y1], [x2, y2], [x1, y2]], dtype=np.float32
            )
            detections.append((box_poly, VEHICLE_CLASSES[cls_id], (x1, y1, x2, y2)))
        return detections

    def _match(self, polygons, areas, detections):
        """
        For every slot, find the detection that covers the most of it.

        Also tracks, per detection, which slots it overlaps - a single
        vehicle box claiming more than one slot is DOUBLE_SLOT.
        """
        best = [None] * len(polygons)
        claims = [[] for _ in detections]

        for si, (poly, area) in enumerate(zip(polygons, areas)):
            if area <= 0:
                continue
            for di, (box_poly, _, _) in enumerate(detections):
                box_area = cv2.contourArea(box_poly)
                if box_area <= 0:
                    continue
                inter_area, _ = cv2.intersectConvexConvex(poly, box_poly)
                if inter_area <= 0:
                    continue

                coverage = inter_area / area
                if coverage < MIN_COVERAGE:
                    continue

                claims[di].append(si)
                if best[si] is None or coverage > best[si][0]:
                    best[si] = (coverage, di, inter_area, box_area)

        return best, claims

    @staticmethod
    def _reason(coverage: float, inter_area: float, box_area: float, claim_count: int) -> str:
        if claim_count > 1:
            return "DOUBLE_SLOT"

        box_containment = inter_area / box_area if box_area else 0.0
        if coverage >= FULL_COVERAGE and box_containment >= MIN_CONTAINMENT:
            return "OK"
        return "BOUNDARY_INTRUSION"
