"""manga-ocr wrapper: crops a detected block (with padding) and reads it."""
from __future__ import annotations

import numpy as np
from PIL import Image

from ..model_lock import LOAD_LOCK
from .detect import TextBlock

_mocr = None


def get_ocr():
    global _mocr
    if _mocr is None:
        with LOAD_LOCK:  # see model_lock.py: first-time imports must not race with other loaders
            if _mocr is None:
                try:  # use the OS trust store so the first model download works behind HTTPS interception
                    import truststore

                    truststore.inject_into_ssl()
                except ImportError:
                    pass
                from manga_ocr import MangaOcr

                _mocr = MangaOcr()
    return _mocr


def padded_box(block: TextBlock, img_w: int, img_h: int) -> tuple[int, int, int, int]:
    """Block box grown by ~6% of its size (min 8px) on each side, clamped to the image."""
    pad_x = max(8, round((block.x2 - block.x1) * 0.06))
    pad_y = max(8, round((block.y2 - block.y1) * 0.06))
    return (
        max(0, block.x1 - pad_x),
        max(0, block.y1 - pad_y),
        min(img_w, block.x2 + pad_x),
        min(img_h, block.y2 + pad_y),
    )


def read_block(img_rgb: np.ndarray, block: TextBlock) -> str:
    h, w = img_rgb.shape[:2]
    x1, y1, x2, y2 = padded_box(block, w, h)
    return get_ocr()(Image.fromarray(img_rgb[y1:y2, x1:x2])).strip()
