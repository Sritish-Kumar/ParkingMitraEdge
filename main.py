"""
main.py — Phase 0 runner.

No cameras, no queue, no MQTT yet. This only proves that:
  1. the config files load correctly
  2. the fake analyzer produces the scripted timeline
  3. the contracts fit together

Run:  python main.py
"""

from analyzers.fake import FakeAnalyzer
from edge.config import load_cameras


def main():
    cameras = load_cameras("config/cameras.yaml")
    print(f"Loaded {len(cameras)} enabled camera(s)\n")

    analyzer = FakeAnalyzer()

    for cam in cameras.values():
        print(f"{cam.camera_id}  calib={cam.calib_version}  "
              f"{cam.sample_fps} fps  slots={[s.slot_id for s in cam.slots]}")
        analyzer.configure(cam.camera_id, cam.slots)

    cam = next(iter(cameras.values()))
    print(f"\nReplaying the scripted timeline for {cam.camera_id}:")
    print("(no real frames - we pass None, the fake ignores it)\n")

    watch = {1, 29, 31, 59, 61, 150, 199, 205}

    for n in range(1, 251):
        verdicts = analyzer.analyze(cam.camera_id, None)

        if n in watch:
            print(f"--- frame {n:3d} ---")
            for v in verdicts:
                score = f"{v.score:5.1f}" if v.score is not None else "    -"
                print(f"   {v.slot_id}  occupied={str(v.occupied):5s}  "
                      f"score={score}  {v.reason}")
            print()


if __name__ == "__main__":
    main()