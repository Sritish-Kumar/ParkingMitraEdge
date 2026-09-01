"""
main.py — Phase 0 runner.

No queue, no MQTT yet. This only proves that:
  1. the config files load correctly
  2. the real analyzer detects vehicles and matches them to slot polygons
  3. the contracts fit together

Run:  python main.py
"""

import cv2

from analyzers.real import RealAnalyzer
from edge.config import load_site


def main():
    cameras = load_site("config/cameras.yaml").cameras
    print(f"Loaded {len(cameras)} enabled camera(s)\n")

    analyzer = RealAnalyzer()

    for cam in cameras.values():
        print(f"{cam.camera_id}  calib={cam.calib_version}  "
              f"{cam.sample_fps} fps  slots={[s.slot_id for s in cam.slots]}")
        analyzer.configure(cam.camera_id, cam.slots)

    cam = next(iter(cameras.values()))
    cap = cv2.VideoCapture(cam.source)
    if not cap.isOpened():
        print(f"\nCould not open {cam.source}")
        return

    print(f"\nRunning the real analyzer against {cam.camera_id} ({cam.source}):\n")

    watch = {1, 29, 31, 59, 61, 150, 199, 205}

    for n in range(1, 251):
        ok, frame = cap.read()
        if not ok:
            print(f"  (video ended at frame {n})")
            break

        verdicts = analyzer.analyze(cam.camera_id, frame)

        if n in watch:
            print(f"--- frame {n:3d} ---")
            for v in verdicts:
                score = f"{v.score:5.1f}" if v.score is not None else "    -"
                print(f"   {v.slot_id}  occupied={str(v.occupied):5s}  "
                      f"score={score}  {v.reason}")
            print()

    cap.release()


if __name__ == "__main__":
    main()