"""Combining and cleaning up detected text blocks (pure geometry, no models)."""
from __future__ import annotations

from .detect import TextBlock

Box = tuple[int, int, int, int]


def area(b: Box) -> int:
    return max(0, b[2] - b[0]) * max(0, b[3] - b[1])


def intersection(a: Box, b: Box) -> int:
    return max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))


def iou(a: Box, b: Box) -> float:
    inter = intersection(a, b)
    union = area(a) + area(b) - inter
    return inter / union if union else 0.0


def scale_block(b: TextBlock, k: float) -> TextBlock:
    """The block with its box multiplied by k (e.g. upscaled-image coordinates -> original)."""
    return TextBlock(round(b.x1 * k), round(b.y1 * k), round(b.x2 * k), round(b.y2 * k), b.vertical, b.conf)


def merge_detections(a: list[TextBlock], b: list[TextBlock], nms_iou: float = 0.5) -> list[TextBlock]:
    """Union of two detection passes over the same page (same coordinates).

    Passes miss different things (the original image finds a small bubble the upscaled one
    doesn't, and vice versa). Boxes that overlap heavily are the same block; the more
    confident one is kept.
    """
    kept: list[TextBlock] = []
    for blk in sorted(a + b, key=lambda blk: -blk.conf):
        if all(iou(blk.bbox, k.bbox) < nms_iou for k in kept):
            kept.append(blk)
    return kept


def drop_containers(blocks: list[TextBlock], inside: float = 0.8, min_inner: int = 2) -> list[TextBlock]:
    """Remove blocks that swallow two or more other blocks.

    The detector sometimes also emits one big box around neighbouring bubbles. Reading that box
    produces garbage (small text between two bubbles), while the individual blocks inside it read
    well, so the container is dropped. A block counts as inside when `inside` of its area lies
    within the candidate container.
    """
    kept = []
    for a in blocks:
        inner = [
            b
            for b in blocks
            if b is not a and area(b.bbox) < area(a.bbox) and intersection(a.bbox, b.bbox) >= inside * area(b.bbox)
        ]
        if len(inner) < min_inner:
            kept.append(a)
    return kept
