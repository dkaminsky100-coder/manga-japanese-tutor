"""Dev tool: OCR every detected block on original vs upscaled pages.

    python -m scripts.compare_ocr ORIG_DIR UP_DIR
Pages are matched by stem (p1.jpeg <-> p1.png). Detection runs on the upscaled page;
boxes are scaled down for the original so both read the same regions.
"""
import sys
import time
from pathlib import Path

import cv2
import numpy as np

from app.pipeline.detect import TextBlock, detect_blocks
from app.pipeline.ocr import read_block


def load(p):
    return cv2.imdecode(np.fromfile(str(p), np.uint8), cv2.IMREAD_COLOR)


def main(orig_dir, up_dir):
    for up in sorted(Path(up_dir).glob("p*.png")):
        orig = next(Path(orig_dir).glob(up.stem + ".*"))
        up_img, o_img = load(up), load(orig)
        sx, sy = o_img.shape[1] / up_img.shape[1], o_img.shape[0] / up_img.shape[0]
        t = time.time()
        blocks = detect_blocks(up_img)
        print(f"\n== {up.stem}: {len(blocks)} blocks (detect {time.time()-t:.1f}s)")
        up_rgb, o_rgb = up_img[:, :, ::-1].copy(), o_img[:, :, ::-1].copy()
        for i, b in enumerate(blocks, 1):
            ob = TextBlock(round(b.x1 * sx), round(b.y1 * sy), round(b.x2 * sx), round(b.y2 * sy), b.vertical, b.conf)
            a, c = read_block(o_rgb, ob), read_block(up_rgb, b)
            print(f"{i:>2} orig: {a}\n   up  : {c}{'' if a == c else '   <-- differs'}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
