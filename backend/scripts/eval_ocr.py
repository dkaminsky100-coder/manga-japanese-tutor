"""Dev tool: score the page-reading pipeline against a hand-made answer key.

    python -m scripts.eval_ocr GROUND_TRUTH.json UPSCALED_DIR ORIGINAL_DIR [--show]

GROUND_TRUTH.json: [{"page": "p1", "bbox": [x1,y1,x2,y2], "text": "..."}] with boxes in the
*upscaled* page's pixels. Pages are UPSCALED_DIR/<page>.png and ORIGINAL_DIR/<page>.*.

Runs app.pipeline.runner.read_page twice - detection on the original only, and on the original
plus the upscaled page (what the server does when WAIFU2X_EXE is set) - and reports character
error rate (CER) and exact matches. Scores use a *loose* normalization (see `normalize`) so that
things a human transcriber can't judge reliably (how many dots or exclamation marks, small vs
full-size kana, spacing) don't count as errors.

Caveat: an answer key this small (a few dozen bubbles) is only good for catching regressions and
big differences; don't tune thresholds to it.
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

import cv2
import numpy as np

from app.pipeline.blocks import area, intersection, iou
from app.pipeline.runner import read_page

_SMALL = str.maketrans("ぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮ", "あいうえおつやゆよわアイウエオツヤユヨワ")


def normalize(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).translate(_SMALL)
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"[.・。､、…]+", ".", s)  # any run of dots / ellipsis
    s = re.sub(r"!+", "!", s)
    s = re.sub(r"\?+", "?", s)
    s = re.sub(r"[ー〜~～―—-]+", "ー", s)
    return s


def levenshtein(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _load(path: Path) -> np.ndarray:
    img = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_COLOR)
    assert img is not None, path
    return img


def hypothesis(read: list, box: list[float]) -> str:
    """What the pipeline read for an answer-key box: the block matching it, or - when the key
    spans several blocks (two bubbles read as one) - the blocks inside it, right to left."""
    best = max(read, key=lambda r: iou(r[0].bbox, box))
    if iou(best[0].bbox, box) >= 0.5:
        return best[1]
    inside = [r for r in read if intersection(box, r[0].bbox) >= 0.7 * area(r[0].bbox)]
    return "".join(t for b, t in sorted(inside, key=lambda r: -r[0].x2))


def main(argv: list[str]) -> None:
    show = "--show" in argv
    gt_path, up_dir, orig_dir = [a for a in argv if a != "--show"][:3]
    gt = json.loads(Path(gt_path).read_text(encoding="utf-8"))

    reads: dict[str, dict[str, list]] = {"original only": {}, "original + upscaled": {}}
    scale: dict[str, float] = {}
    for page in sorted({g["page"] for g in gt}):
        orig = _load(next(Path(orig_dir).glob(page + ".*")))
        up = _load(Path(up_dir) / f"{page}.png")
        scale[page] = orig.shape[1] / up.shape[1]
        reads["original only"][page] = read_page(orig)
        reads["original + upscaled"][page] = read_page(orig, up)

    total = sum(len(normalize(g["text"])) for g in gt)
    print(f"{len(gt)} answer-key blocks, {total} reference characters\n")
    outs: dict[str, list[str]] = {}
    for mode, per_page in reads.items():
        outs[mode] = [hypothesis(per_page[g["page"]], [v * scale[g["page"]] for v in g["bbox"]]) for g in gt]
        edits = [levenshtein(normalize(o), normalize(g["text"])) for o, g in zip(outs[mode], gt)]
        print(f"{mode:22} CER {100 * sum(edits) / total:5.1f}%   exact {sum(e == 0 for e in edits):2}/{len(gt)}")

    if show:
        print()
        for i, g in enumerate(gt):
            bad = [m for m in outs if normalize(outs[m][i]) != normalize(g["text"])]
            if bad:
                print(f"[{g['page']} {g['bbox']}] ref: {g['text']}")
                for m in outs:
                    print(f"    {'BAD' if m in bad else 'ok '} {m:22} {outs[m][i]}")


if __name__ == "__main__":
    main(sys.argv[1:])
