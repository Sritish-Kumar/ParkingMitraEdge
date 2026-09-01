"""
tools/bake_dashboard.py — make dashboard.html standalone.

Browsers block fetch() on file:// URLs, so the normal dashboard needs a
web server just to read your slot config. This script inlines the slot
JSON and the photo directly into the HTML, so there is nothing left to
fetch and you can open the file by double-clicking it.

Usage:
    python tools/bake_dashboard.py
    python tools/bake_dashboard.py --slots config/slots/CAM_02.json \
                                   --photo demo/lot2.jpg \
                                   --out  dashboard_cam02.html

Re-run it whenever you recalibrate.
"""

import argparse
import base64
import json
import mimetypes
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", default="dashboard.html")
    ap.add_argument("--slots", default="config/slots/CAM_01.json")
    ap.add_argument("--photo", default="demo/lot.jpg")
    ap.add_argument("--out", default="dashboard_standalone.html")
    args = ap.parse_args()

    html = Path(args.template).read_text(encoding="utf-8")
    slots = json.loads(Path(args.slots).read_text())

    photo = Path(args.photo).read_bytes()
    mime = mimetypes.guess_type(args.photo)[0] or "image/jpeg"
    data_uri = f"data:{mime};base64,{base64.b64encode(photo).decode()}"

    # Warn loudly - this is the mistake that puts polygons in the wrong place.
    try:
        import struct
        print(f"  slots file says image_size = {slots['image_size']}")
        print(f"  make sure {args.photo} is exactly that size")
    except Exception:
        pass

    html = html.replace(
        'const SLOTS_URL = "config/slots/CAM_01.json";',
        f"const SLOTS_INLINE = {json.dumps(slots)};",
    )
    html = html.replace(
        'const PHOTO_URL = "demo/lot.jpg";',
        f'const PHOTO_URL = "{data_uri}";',
    )
    html = html.replace(
        "  const res  = await fetch(SLOTS_URL);\n  const data = await res.json();",
        "  const data = SLOTS_INLINE;",
    )
    html = html.replace(
        "`Could not load ${SLOTS_URL}. `",
        "`Could not draw the slots. `",
    )

    Path(args.out).write_text(html, encoding="utf-8")
    size_kb = len(html.encode()) / 1024
    print(f"\nwrote {args.out}  ({size_kb:.0f} KB)  "
          f"{len(slots['slots'])} slots baked in")
    print("open it directly in a browser - no server needed")


if __name__ == "__main__":
    main()