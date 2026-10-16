"""Text-block detection with comic-text-detector (ONNX).

The model takes a 1024x1024 letterboxed image and returns three maps; only the
YOLO-style `blk` output ([cx, cy, w, h, objectness, cls0, cls1] per candidate) is
used here. Boxes come back in the original image's pixel coordinates.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort

from ..db import DATA_DIR

MODEL_PATH = DATA_DIR / "models" / "comictextdetector.pt.onnx"
INPUT_SIZE = 1024
HORIZONTAL_ASPECT = 1.6  # width/height above which a block is treated as horizontal text

_session: ort.InferenceSession | None = None


@dataclass
class TextBlock:
    x1: int
    y1: int
    x2: int
    y2: int
    vertical: bool
    conf: float

    @property
    def bbox(self) -> tuple[int, int, int, int]:
        return self.x1, self.y1, self.x2, self.y2


def _providers() -> list[str]:
    # DirectML (AMD/any DX12 GPU) is used if onnxruntime-directml is installed.
    available = ort.get_available_providers()
    return [p for p in ("DmlExecutionProvider", "CPUExecutionProvider") if p in available]


def get_session() -> ort.InferenceSession:
    global _session
    if _session is None:
        if not MODEL_PATH.is_file():
            raise FileNotFoundError(f"Detector model missing: {MODEL_PATH}")
        _session = ort.InferenceSession(str(MODEL_PATH), providers=_providers())
    return _session


def letterbox(img: np.ndarray) -> tuple[np.ndarray, float]:
    """Scale the longest side to INPUT_SIZE and pad bottom/right with black."""
    h, w = img.shape[:2]
    scale = INPUT_SIZE / max(h, w)
    nh, nw = round(h * scale), round(w * scale)
    canvas = np.zeros((INPUT_SIZE, INPUT_SIZE, 3), np.uint8)
    canvas[:nh, :nw] = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC)
    return canvas, scale


def decode_blocks(
    pred: np.ndarray,
    scale: float,
    img_w: int,
    img_h: int,
    conf_thresh: float = 0.4,
    iou_thresh: float = 0.35,
) -> list[TextBlock]:
    """Turn raw YOLO candidates [N,7] into NMS-filtered boxes in original-image pixels."""
    cls = pred[:, 5:7]
    conf = pred[:, 4] * cls.max(axis=1)
    keep = conf > conf_thresh
    if not keep.any():
        return []
    pred, conf = pred[keep], conf[keep]

    cx, cy, w, h = pred[:, 0], pred[:, 1], pred[:, 2], pred[:, 3]
    boxes = np.stack([cx - w / 2, cy - h / 2, w, h], axis=1) / scale
    idx = cv2.dnn.NMSBoxes(boxes.tolist(), conf.tolist(), conf_thresh, iou_thresh)

    blocks = []
    for i in np.array(idx).reshape(-1):
        x, y, bw, bh = boxes[i]
        x1, y1 = max(0, int(round(x))), max(0, int(round(y)))
        x2, y2 = min(img_w, int(round(x + bw))), min(img_h, int(round(y + bh)))
        if x2 - x1 < 4 or y2 - y1 < 4:
            continue
        # Manga text is vertical unless the block is clearly wide; a squarish block of several
        # columns (3 short columns of a stuttering line) must not be mistaken for horizontal text.
        vertical = (x2 - x1) <= HORIZONTAL_ASPECT * (y2 - y1)
        blocks.append(TextBlock(x1, y1, x2, y2, vertical=vertical, conf=float(conf[i])))
    return reading_order(blocks)


def reading_order(blocks: list[TextBlock]) -> list[TextBlock]:
    """Approximate manga reading order: right-to-left by right edge, ties top-to-bottom.

    This ignores panel structure, so it is only a heuristic for numbering bubbles."""
    return sorted(blocks, key=lambda b: (-b.x2, b.y1))


def _model_input(img_bgr: np.ndarray) -> tuple[np.ndarray, float]:
    canvas, scale = letterbox(img_bgr)
    return canvas[:, :, ::-1].transpose(2, 0, 1)[None].astype(np.float32) / 255.0, scale


def detect_blocks(img_bgr: np.ndarray, conf_thresh: float = 0.4) -> list[TextBlock]:
    h, w = img_bgr.shape[:2]
    x, scale = _model_input(img_bgr)
    sess = get_session()
    blk = sess.run(["blk"], {sess.get_inputs()[0].name: x})[0][0]
    return decode_blocks(blk, scale, w, h, conf_thresh)


def detect_file(path: str | Path, conf_thresh: float = 0.4) -> list[TextBlock]:
    img = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"Cannot read image: {path}")
    return detect_blocks(img, conf_thresh)
