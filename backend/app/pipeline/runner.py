"""Per-page analysis job: (optional upscale) -> detect -> OCR -> store blocks.

Jobs run on a single worker thread: the models are CPU-bound and not thread-safe, and
one worker keeps results arriving in the order pages were requested.
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np

from .. import db
from .detect import detect_blocks
from .ocr import read_block
from .upscale import ensure_upscaled

log = logging.getLogger(__name__)
_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="analysis")


def _read_image(path) -> np.ndarray:
    img = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"Cannot read image: {path}")
    return img


def enqueue(page_id: int) -> str:
    """Queue a page for analysis unless it already has a row. Returns its current status."""
    with db.connect() as conn:
        row = conn.execute("SELECT status FROM page_analysis WHERE page_id = ?", (page_id,)).fetchone()
        if row:
            return row["status"]
        if not conn.execute("SELECT 1 FROM pages WHERE id = ?", (page_id,)).fetchone():
            raise LookupError(page_id)
        conn.execute("INSERT INTO page_analysis (page_id, status) VALUES (?, 'pending')", (page_id,))
    _pool.submit(_run, page_id)
    return "pending"


def warm_up() -> None:
    """Load the detector and OCR models on the worker thread so the first page isn't slow."""

    def load() -> None:
        try:
            from .detect import get_session
            from .ocr import get_ocr

            get_session()
            get_ocr()
        except Exception:  # noqa: BLE001 - a missing model is reported when a page is analysed
            log.exception("model warm-up failed")

    _pool.submit(load)


def requeue_unfinished() -> None:
    """Jobs interrupted by a restart are left pending/running; run them again."""
    with db.connect() as conn:
        ids = [
            r["page_id"]
            for r in conn.execute(
                "SELECT page_id FROM page_analysis WHERE status IN ('pending','running') ORDER BY page_id"
            )
        ]
    for pid in ids:
        _pool.submit(_run, pid)


def _run(page_id: int) -> None:
    try:
        with db.connect() as conn:
            conn.execute("UPDATE page_analysis SET status='running' WHERE page_id=?", (page_id,))
            row = conn.execute("SELECT chapter_id, filename FROM pages WHERE id=?", (page_id,)).fetchone()
        if row is None:  # chapter deleted while queued
            return
        path = db.LIBRARY_DIR / str(row["chapter_id"]) / row["filename"]
        up = ensure_upscaled(path)
        img = _read_image(up or path)
        # Boxes are stored in the *original* page's pixel space so the frontend can map
        # them onto the displayed image regardless of upscaling.
        scale = 1.0
        if up is not None:
            scale = _read_image(path).shape[1] / img.shape[1]

        t0 = time.perf_counter()
        blocks = detect_blocks(img)
        t1 = time.perf_counter()
        rgb = img[:, :, ::-1].copy()
        texts = [read_block(rgb, b) for b in blocks]
        t2 = time.perf_counter()

        with db.connect() as conn:
            conn.execute("DELETE FROM blocks WHERE page_id=?", (page_id,))
            for i, (b, text) in enumerate(zip(blocks, texts)):
                if not text:
                    continue
                conn.execute(
                    "INSERT INTO blocks (page_id, idx, x1, y1, x2, y2, vertical, conf, text) VALUES (?,?,?,?,?,?,?,?,?)",
                    (page_id, i, round(b.x1 * scale), round(b.y1 * scale), round(b.x2 * scale),
                     round(b.y2 * scale), int(b.vertical), b.conf, text),
                )
            conn.execute(
                "UPDATE page_analysis SET status='done', error=NULL, detect_ms=?, ocr_ms=?, upscaled=? WHERE page_id=?",
                (round((t1 - t0) * 1000), round((t2 - t1) * 1000), int(up is not None), page_id),
            )
    except Exception as e:  # noqa: BLE001 - record any failure so the UI can show it
        log.exception("analysis failed for page %s", page_id)
        with db.connect() as conn:
            conn.execute("UPDATE page_analysis SET status='error', error=? WHERE page_id=?", (str(e)[:500], page_id))


def get_analysis(page_id: int) -> dict:
    with db.connect() as conn:
        a = conn.execute("SELECT * FROM page_analysis WHERE page_id=?", (page_id,)).fetchone()
        blocks = conn.execute(
            "SELECT id, idx, x1, y1, x2, y2, vertical, conf, text FROM blocks WHERE page_id=? ORDER BY idx",
            (page_id,),
        ).fetchall()
    return {
        "status": a["status"] if a else "none",
        "error": a["error"] if a else None,
        "upscaled": bool(a["upscaled"]) if a else False,
        "detect_ms": a["detect_ms"] if a else None,
        "ocr_ms": a["ocr_ms"] if a else None,
        "blocks": [
            {
                "id": b["id"],
                "bbox": [b["x1"], b["y1"], b["x2"], b["y2"]],
                "vertical": bool(b["vertical"]),
                "conf": b["conf"],
                "text": b["text"],
            }
            for b in blocks
        ],
    }
