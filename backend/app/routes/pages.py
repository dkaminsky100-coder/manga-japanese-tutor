import logging

from fastapi import APIRouter, HTTPException

from .. import db
from ..nlp import translate as translator
from ..pipeline import runner

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

PREFETCH_AHEAD = 2


@router.get("/pages/{page_id}/analysis")
def page_analysis(page_id: int):
    """Return the page's detected blocks, starting analysis (and prefetching the next pages) if needed."""
    try:
        runner.enqueue(page_id)
    except LookupError:
        raise HTTPException(404, "Page not found")
    with db.connect() as conn:
        nxt = conn.execute(
            """SELECT p2.id FROM pages p1 JOIN pages p2 ON p2.chapter_id = p1.chapter_id AND p2.idx > p1.idx
               WHERE p1.id = ? ORDER BY p2.idx LIMIT ?""",
            (page_id, PREFETCH_AHEAD),
        ).fetchall()
    for r in nxt:
        runner.enqueue(r["id"])
    return runner.get_analysis(page_id)


@router.post("/blocks/{block_id}/translate")
def translate_block(block_id: int):
    """Rough local machine translation of a block's text, cached by text."""
    with db.connect() as conn:
        row = conn.execute("SELECT text FROM blocks WHERE id = ?", (block_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Block not found")
        text = row["text"]
        cached = conn.execute("SELECT translation, model FROM translations WHERE text = ?", (text,)).fetchone()
    if cached:
        return {"translation": cached["translation"], "model": cached["model"], "cached": True}

    try:
        result = translator.translate(text)
    except Exception as e:  # noqa: BLE001 - model missing / download failed / out of memory
        log.exception("translation failed for block %s", block_id)
        raise HTTPException(503, f"Translation model unavailable: {e}")

    with db.connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO translations (text, translation, model) VALUES (?,?,?)",
            (text, result, translator.MODEL_NAME),
        )
    return {"translation": result, "model": translator.MODEL_NAME, "cached": False}
