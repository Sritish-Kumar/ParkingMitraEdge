"""
tools/calibrate.py — draw parking slots on a still frame, once per camera.

Usage:
    python tools/calibrate.py CAM_01 path/to/still.jpg

Controls:
    left click   add a corner (4 per slot)
    u            undo last corner
    r            reset current slot
    s            save and quit
    q            quit without saving

After 4 corners it asks for a slot id in the terminal, then starts
the next slot. Output goes to config/slots/<CAM_ID>.json
"""

import json
import sys
from pathlib import Path

import cv2
import numpy as np

CORNERS_PER_SLOT = 4


def centroid(points):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return [round(sum(xs) / len(xs), 1), round(sum(ys) / len(ys), 1)]


def slot_angle(points):
    """Angle of the slot's long axis, in degrees. Used for orientation checks."""
    p = np.array(points, dtype=np.float32)
    rect = cv2.minAreaRect(p)          # ((cx, cy), (w, h), angle)
    (_, _), (w, h), angle = rect
    if w < h:                          # make the angle describe the LONG side
        angle += 90
    return round(float(angle), 1)


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)

    camera_id, image_path = sys.argv[1], sys.argv[2]

    base = cv2.imread(image_path)
    if base is None:
        print(f"Could not read image: {image_path}")
        sys.exit(1)

    height, width = base.shape[:2]
    slots = []
    current = []

    def redraw():
        img = base.copy()
        for s in slots:                                   # finished slots, green
            pts = np.array(s["polygon"], dtype=np.int32)
            cv2.polylines(img, [pts], True, (0, 200, 0), 2)
            cv2.putText(img, s["slot_id"], tuple(pts[0]),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 0), 2)
        for pt in current:                                # in-progress, red
            cv2.circle(img, tuple(pt), 5, (0, 0, 255), -1)
        if len(current) > 1:
            cv2.polylines(img, [np.array(current, dtype=np.int32)],
                          False, (0, 0, 255), 2)
        cv2.imshow("calibrate", img)

    def on_mouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN and len(current) < CORNERS_PER_SLOT:
            current.append([x, y])
            redraw()

    cv2.namedWindow("calibrate", cv2.WINDOW_NORMAL)
    cv2.setMouseCallback("calibrate", on_mouse)
    print(f"\nClick 4 corners per slot. 's' to save, 'q' to quit.\n")
    redraw()

    while True:
        if len(current) == CORNERS_PER_SLOT:
            cv2.waitKey(1)
            slot_id = input("  slot id (e.g. A07), blank to discard: ").strip()
            if slot_id:
                slots.append({
                    "slot_id": slot_id,
                    "polygon": [list(p) for p in current],
                    "center": centroid(current),
                    "angle": slot_angle(current),
                })
                print(f"  saved {slot_id}  ({len(slots)} slot(s) so far)")
            current.clear()
            redraw()
            continue

        key = cv2.waitKey(20) & 0xFF
        if key == ord("u") and current:
            current.pop()
            redraw()
        elif key == ord("r"):
            current.clear()
            redraw()
        elif key == ord("q"):
            print("quit without saving")
            break
        elif key == ord("s"):
            out = Path("config/slots") / f"{camera_id}.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps({
                "camera_id": camera_id,
                "calib_version": "v1",
                "image_size": [width, height],
                "slots": slots,
            }, indent=2))
            print(f"\nWrote {len(slots)} slot(s) to {out}")
            break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()