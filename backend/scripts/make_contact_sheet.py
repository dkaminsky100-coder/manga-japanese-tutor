"""Dev tool: crop every detected block, enlarge and number it, and tile them into one image per
page so the text can be transcribed by eye (building an OCR answer key).

    python -m scripts.make_contact_sheet OUT_DIR IMAGE [IMAGE ...]

Also writes blocks_<stem>.json with each block's index and bbox (in the image's pixels).
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np

from app.pipeline.detect import detect_blocks
from app.pipeline.ocr import padded_box

CELL_H = 420
LABEL_H = 34


def tile(cells: list[np.ndarray], max_width: int = 1500) -> np.ndarray:
    rows, row, width = [], [], 0
    for c in cells:
        if row and width + c.shape[1] > max_width:
            rows.append(row)
            row, width = [], 0
        row.append(c)
        width += c.shape[1]
    if row:
        rows.append(row)
    out_w = max(sum(c.shape[1] for c in r) for r in rows)
    sheet = []
    for r in rows:
        h = max(c.shape[0] for c in r)
        line = np.full((h, out_w, 3), 255, np.uint8)
        x = 0
        for c in r:
            line[: c.shape[0], x : x + c.shape[1]] = c
            x += c.shape[1]
        sheet.append(line)
    return np.vstack(sheet)


def main(out_dir: str, paths: list[str]) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for p in paths:
        img = cv2.imdecode(np.fromfile(p, np.uint8), cv2.IMREAD_COLOR)
        h, w = img.shape[:2]
        blocks = detect_blocks(img)
        cells, meta = [], []
        for i, b in enumerate(blocks):
            x1, y1, x2, y2 = padded_box(b, w, h)
            crop = img[y1:y2, x1:x2]
            scale = CELL_H / crop.shape[0]
            crop = cv2.resize(crop, (max(1, round(crop.shape[1] * scale)), CELL_H), interpolation=cv2.INTER_CUBIC)
            cell = np.full((CELL_H + LABEL_H, crop.shape[1] + 10, 3), 255, np.uint8)
            cell[LABEL_H : LABEL_H + CELL_H, 5 : 5 + crop.shape[1]] = crop
            cv2.putText(cell, f"#{i}", (6, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
            cv2.rectangle(cell, (0, 0), (cell.shape[1] - 1, cell.shape[0] - 1), (180, 180, 180), 1)
            cells.append(cell)
            meta.append({"idx": i, "bbox": list(b.bbox)})
        stem = Path(p).stem
        cv2.imencode(".png", tile(cells))[1].tofile(str(out / f"sheet_{stem}.png"))
        (out / f"blocks_{stem}.json").write_text(json.dumps(meta), encoding="utf-8")
        print(stem, len(blocks), "blocks")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
