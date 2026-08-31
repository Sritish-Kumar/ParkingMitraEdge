"""
tools/make_test_video.py — turn a still image into a video file.

You need something for CameraWorker to open. The input images are played
in order, then repeated, so a single image becomes a still-camera stream
and multiple images become a simple looping sequence.

Usage:
    python tools/make_test_video.py parking.jpg testdata/lot1.mp4
    python tools/make_test_video.py frame1.jpg frame2.jpg testdata/lot2.mp4
    python tools/make_test_video.py demo-img/*.jpg testdata/lot3.mp4 --seconds 60

The frame counter makes it obvious the pipeline is reading live frames;
pass --no-frame-counter when you need unmodified source images.
"""

import argparse
from glob import glob
from pathlib import Path

import cv2


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="+",
        metavar="IMAGE_OR_OUTPUT",
        help="one or more input images followed by the output MP4 path",
    )
    parser.add_argument(
        "--seconds", type=float, default=60, help="total video length (default: 60)"
    )
    parser.add_argument(
        "--fps", type=int, default=25, help="video frame rate (default: 25)"
    )
    parser.add_argument(
        "--image-seconds",
        type=float,
        default=1,
        help="seconds to show each image before advancing (default: 1)",
    )
    parser.add_argument(
        "--no-frame-counter", action="store_true", help="do not draw a frame counter"
    )
    args = parser.parse_args()

    if len(args.paths) < 2:
        parser.error("provide at least one input image and an output video path")
    if args.seconds <= 0 or args.fps <= 0 or args.image_seconds <= 0:
        parser.error("--seconds, --fps, and --image-seconds must be greater than zero")

    image_paths = []
    for image_spec in args.paths[:-1]:
        matches = sorted(glob(image_spec))
        image_paths.extend(matches or [image_spec])
    out_path = Path(args.paths[-1])
    images = []
    for image_path in image_paths:
        image = cv2.imread(image_path)
        if image is None:
            raise SystemExit(f"could not read image: {image_path}")
        images.append(image)

    h, w = images[0].shape[:2]
    normalized_images = []
    for image_path, image in zip(image_paths, images):
        if image.shape[:2] != (h, w):
            print(f"resizing {image_path} from {image.shape[1]}x{image.shape[0]} to {w}x{h}")
            image = cv2.resize(image, (w, h), interpolation=cv2.INTER_AREA)
        normalized_images.append(image)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(out_path), cv2.VideoWriter.fourcc(*"mp4v"), args.fps, (w, h)
    )
    if not writer.isOpened():
        raise SystemExit(f"could not create video: {out_path}")

    total_frames = round(args.seconds * args.fps)
    frames_per_image = max(1, round(args.image_seconds * args.fps))
    for frame_number in range(total_frames):
        image_index = (frame_number // frames_per_image) % len(normalized_images)
        frame = normalized_images[image_index].copy()
        if not args.no_frame_counter:
            cv2.putText(
                frame,
                f"frame {frame_number}",
                (20, h - 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                (0, 255, 255),
                2,
            )
        writer.write(frame)

    writer.release()
    print(
        f"wrote {out_path}  {w}x{h}  {args.seconds:g}s @ {args.fps}fps "
        f"from {len(normalized_images)} image(s)"
    )


if __name__ == "__main__":
    main()
