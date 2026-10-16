from fastapi import APIRouter, HTTPException

from .. import db
from ..pipeline import runner

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
