"""Dev tool: draw detected text blocks on page images.

    python -m scripts.draw_boxes OUT_DIR IMAGE [IMAGE ...]
"""
import sys
from pathlib import Path

import cv2
import numpy as np

from app.pipeline.detect import detect_blocks


def main(out_dir: str, paths: list[str]) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for p in paths:
        img = cv2.imdecode(np.fromfile(p, np.uint8), cv2.IMREAD_COLOR)
        blocks = detect_blocks(img)
        for n, b in enumerate(blocks, 1):
            color = (0, 0, 255) if b.vertical else (255, 0, 0)
            cv2.rectangle(img, (b.x1, b.y1), (b.x2, b.y2), color, 3)
            cv2.putText(img, f"{n} {b.conf:.2f}", (b.x1, max(20, b.y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)
        dst = out / f"boxes_{Path(p).stem}.png"
        cv2.imencode(".png", img)[1].tofile(str(dst))
        print(Path(p).name, len(blocks), "blocks ->", dst)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
