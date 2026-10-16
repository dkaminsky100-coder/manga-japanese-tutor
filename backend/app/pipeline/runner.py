"""Per-page analysis job: detect text blocks -> OCR the original page -> store blocks.

Detection runs on the original page and, when an upscaler is configured, on an upscaled copy too
(the passes find different blocks). OCR always reads crops of the *original* page: on the answer
key, reading upscaled crops made more mistakes (the upscaler's smoothing confuses similar kana).

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
from .blocks import drop_containers, iou, merge_detections, scale_block
from .detect import TextBlock, detect_blocks, reading_order
from .ocr import read_block
from .upscale import ensure_upscaled

# Bump when a pipeline change should re-read pages that were already analysed.
PIPELINE_VERSION = 2

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
        row = conn.execute("SELECT status, version FROM page_analysis WHERE page_id = ?", (page_id,)).fetchone()
        if row:
            if row["status"] in ("done", "error") and row["version"] < PIPELINE_VERSION:
                # analysed by an older pipeline: read it again (old blocks stay visible meanwhile)
                conn.execute("UPDATE page_analysis SET status='pending' WHERE page_id = ?", (page_id,))
                _pool.submit(_run, page_id)
                return "pending"
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
            from ..nlp.translate import warm_up as warm_translator

            warm_translator()
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


def detect_page(orig_bgr: np.ndarray, up_bgr: np.ndarray | None = None) -> list[TextBlock]:
    """Text blocks of a page in the original image's pixel coordinates, in reading order."""
    blocks = detect_blocks(orig_bgr)
    if up_bgr is not None:
        k = orig_bgr.shape[1] / up_bgr.shape[1]
        blocks = merge_detections(blocks, [scale_block(b, k) for b in detect_blocks(up_bgr)])
    return reading_order(drop_containers(blocks))


def read_page(orig_bgr: np.ndarray, up_bgr: np.ndarray | None = None) -> list[tuple[TextBlock, str]]:
    """Detect and OCR a whole page: [(block, text)] in reading order."""
    blocks = detect_page(orig_bgr, up_bgr)
    rgb = orig_bgr[:, :, ::-1].copy()
    return [(b, read_block(rgb, b)) for b in blocks]


def _run(page_id: int) -> None:
    try:
        with db.connect() as conn:
            conn.execute("UPDATE page_analysis SET status='running' WHERE page_id=?", (page_id,))
            row = conn.execute("SELECT chapter_id, filename FROM pages WHERE id=?", (page_id,)).fetchone()
        if row is None:  # chapter deleted while queued
            return
        path = db.LIBRARY_DIR / str(row["chapter_id"]) / row["filename"]
        orig = _read_image(path)
        up_path = ensure_upscaled(path)
        up = _read_image(up_path) if up_path is not None else None

        t0 = time.perf_counter()
        blocks = detect_page(orig, up)
        t1 = time.perf_counter()
        rgb = orig[:, :, ::-1].copy()
        texts = [read_block(rgb, b) for b in blocks]
        t2 = time.perf_counter()

        with db.connect() as conn:
            corrections = [
                dict(r) for r in conn.execute(
                    "SELECT x1, y1, x2, y2, vertical, conf, text, ocr_text FROM blocks WHERE page_id=? AND edited=1",
                    (page_id,),
                )
            ]
            conn.execute("DELETE FROM blocks WHERE page_id=?", (page_id,))
            inserted = []  # (idx, bbox) of the blocks just read
            for i, (b, text) in enumerate(zip(blocks, texts)):
                if not text:
                    continue
                conn.execute(
                    "INSERT INTO blocks (page_id, idx, x1, y1, x2, y2, vertical, conf, text, ocr_text) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (page_id, i, b.x1, b.y1, b.x2, b.y2, int(b.vertical), b.conf, text, text),
                )
                inserted.append((i, b.bbox))
            _restore_corrections(conn, page_id, corrections, inserted)
            conn.execute(
                "UPDATE page_analysis SET status='done', error=NULL, detect_ms=?, ocr_ms=?, upscaled=?, version=? WHERE page_id=?",
                (round((t1 - t0) * 1000), round((t2 - t1) * 1000), int(up is not None), PIPELINE_VERSION, page_id),
            )
    except Exception as e:  # noqa: BLE001 - record any failure so the UI can show it
        log.exception("analysis failed for page %s", page_id)
        with db.connect() as conn:
            conn.execute("UPDATE page_analysis SET status='error', error=? WHERE page_id=?", (str(e)[:500], page_id))


def _restore_corrections(conn, page_id: int, corrections: list[dict], inserted: list[tuple[int, tuple]]) -> None:
    """Re-apply the user's text corrections after a page was read again.

    Each correction goes to the new block it overlaps most (IoU >= 0.5). If the bubble is no
    longer detected the corrected block is kept as it was, so a user's work is never lost.
    """
    taken: set[int] = set()
    next_idx = max((i for i, _ in inserted), default=-1) + 1
    for old in corrections:
        old_box = (old["x1"], old["y1"], old["x2"], old["y2"])
        scored = [(iou(box, old_box), idx) for idx, box in inserted if idx not in taken]
        best_iou, best_idx = max(scored, default=(0.0, -1))
        if best_iou >= 0.5:
            taken.add(best_idx)
            conn.execute(
                "UPDATE blocks SET text=?, edited=(? != ocr_text) WHERE page_id=? AND idx=?",
                (old["text"], old["text"], page_id, best_idx),
            )
        else:
            conn.execute(
                "INSERT INTO blocks (page_id, idx, x1, y1, x2, y2, vertical, conf, text, ocr_text, edited) VALUES (?,?,?,?,?,?,?,?,?,?,1)",
                (page_id, next_idx, old["x1"], old["y1"], old["x2"], old["y2"], old["vertical"], old["conf"],
                 old["text"], old["ocr_text"] or old["text"]),
            )
            next_idx += 1


MAX_TEXT_CHARS = 400


def clean_text(text: str) -> str:
    """Normalize user-entered block text like the OCR does: no whitespace (Japanese is unspaced)."""
    return "".join(text.split())


def _block_json(b) -> dict:
    return {
        "id": b["id"],
        "bbox": [b["x1"], b["y1"], b["x2"], b["y2"]],
        "vertical": bool(b["vertical"]),
        "conf": b["conf"],
        "text": b["text"],
        "ocr_text": b["ocr_text"] if b["ocr_text"] is not None else b["text"],
        "edited": bool(b["edited"]),
        **_language_analysis(b["text"]),
    }


_BLOCK_COLUMNS = "id, idx, x1, y1, x2, y2, vertical, conf, text, ocr_text, edited"


def get_block(block_id: int) -> dict | None:
    with db.connect() as conn:
        row = conn.execute(f"SELECT {_BLOCK_COLUMNS} FROM blocks WHERE id=?", (block_id,)).fetchone()
    return _block_json(row) if row else None


def edit_block(block_id: int, text: str) -> dict | None:
    """Set a block's text to the user's correction (already cleaned). None if there is no such block."""
    with db.connect() as conn:
        cur = conn.execute(
            "UPDATE blocks SET text=?, edited=(? != COALESCE(ocr_text, '')) WHERE id=?", (text, text, block_id)
        )
        if cur.rowcount == 0:
            return None
    return get_block(block_id)


def revert_block(block_id: int) -> dict | None:
    """Undo a correction: show the OCR text again."""
    with db.connect() as conn:
        cur = conn.execute("UPDATE blocks SET text=COALESCE(ocr_text, text), edited=0 WHERE id=?", (block_id,))
        if cur.rowcount == 0:
            return None
    return get_block(block_id)


def get_analysis(page_id: int) -> dict:
    with db.connect() as conn:
        a = conn.execute("SELECT * FROM page_analysis WHERE page_id=?", (page_id,)).fetchone()
        blocks = conn.execute(
            f"SELECT {_BLOCK_COLUMNS} FROM blocks WHERE page_id=? ORDER BY idx",
            (page_id,),
        ).fetchall()
    return {
        "status": a["status"] if a else "none",
        "error": a["error"] if a else None,
        "upscaled": bool(a["upscaled"]) if a else False,
        "detect_ms": a["detect_ms"] if a else None,
        "ocr_ms": a["ocr_ms"] if a else None,
        "blocks": [_block_json(b) for b in blocks],
    }


def _language_analysis(text: str) -> dict:
    """Tokens (furigana, dictionary entries) and compounds for a block; empty if analysis fails."""
    try:
        from ..nlp.analyze import analyze_text

        return analyze_text(text)
    except Exception:  # noqa: BLE001 - a NLP failure must not hide the OCR text
        log.exception("language analysis failed for %r", text)
        return {"tokens": [], "compounds": [], "grammar": []}
