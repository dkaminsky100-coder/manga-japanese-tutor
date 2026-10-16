import io
import re
import shutil
import zipfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError

from ..db import LIBRARY_DIR, connect
from ..pdf import PdfError, extract_pdf_pages

router = APIRouter(prefix="/api")

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
MAX_PAGES = 500


def _natural_key(name: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name)]


def _collect_images(uploads: list[tuple[str, bytes]]) -> list[tuple[str, bytes]]:
    """Expand .cbz/.zip archives and .pdf files into page images, in natural filename order."""
    images: list[tuple[str, bytes]] = []
    for name, data in uploads:
        ext = Path(name).suffix.lower()
        if ext in (".cbz", ".zip"):
            try:
                with zipfile.ZipFile(io.BytesIO(data)) as zf:
                    for info in zf.infolist():
                        member = Path(info.filename)
                        if info.is_dir() or member.suffix.lower() not in IMAGE_EXTS:
                            continue
                        if "__MACOSX" in member.parts:
                            continue
                        images.append((info.filename, zf.read(info)))
            except zipfile.BadZipFile:
                raise HTTPException(400, f"{name} is not a valid archive")
        elif ext == ".pdf":
            try:
                images.extend(extract_pdf_pages(data, Path(name).stem))
            except PdfError as e:
                raise HTTPException(400, f"{name}: {e}")
        elif ext in IMAGE_EXTS:
            images.append((name, data))
    images.sort(key=lambda it: _natural_key(it[0]))
    return images


@router.post("/chapters")
async def create_chapter(title: str = Form(""), files: list[UploadFile] = File(...)):
    uploads = [(f.filename or "page", await f.read()) for f in files]
    images = _collect_images(uploads)
    if not images:
        raise HTTPException(400, "No images found in upload")
    if len(images) > MAX_PAGES:
        raise HTTPException(400, f"Too many pages (max {MAX_PAGES})")

    # Validate and measure every image before touching the DB or disk.
    decoded = []
    for name, data in images:
        try:
            with Image.open(io.BytesIO(data)) as im:
                im.load()
                decoded.append((name, data, im.format, im.width, im.height))
        except (UnidentifiedImageError, OSError):
            raise HTTPException(400, f"{name} is not a readable image")

    title = title.strip() or Path(uploads[0][0]).stem

    with connect() as conn:
        chapter_id = conn.execute("INSERT INTO chapters (title) VALUES (?)", (title,)).lastrowid
        chapter_dir = LIBRARY_DIR / str(chapter_id)
        chapter_dir.mkdir(parents=True, exist_ok=True)
        try:
            for idx, (name, data, fmt, w, h) in enumerate(decoded):
                filename = f"{idx:04d}.{(fmt or 'png').lower().replace('jpeg', 'jpg')}"
                (chapter_dir / filename).write_bytes(data)
                conn.execute(
                    "INSERT INTO pages (chapter_id, idx, filename, width, height) VALUES (?,?,?,?,?)",
                    (chapter_id, idx, filename, w, h),
                )
        except Exception:
            shutil.rmtree(chapter_dir, ignore_errors=True)
            raise
    return {"id": chapter_id, "title": title, "page_count": len(decoded)}


@router.get("/chapters")
def list_chapters():
    with connect() as conn:
        rows = conn.execute(
            """SELECT c.id, c.title, c.created_at, COUNT(p.id) AS page_count
               FROM chapters c LEFT JOIN pages p ON p.chapter_id = c.id
               GROUP BY c.id ORDER BY c.id DESC"""
        ).fetchall()
    return [dict(r) for r in rows]


@router.get("/chapters/{chapter_id}")
def get_chapter(chapter_id: int):
    with connect() as conn:
        chapter = conn.execute("SELECT id, title FROM chapters WHERE id = ?", (chapter_id,)).fetchone()
        if not chapter:
            raise HTTPException(404, "Chapter not found")
        pages = conn.execute(
            "SELECT id, idx, width, height FROM pages WHERE chapter_id = ? ORDER BY idx", (chapter_id,)
        ).fetchall()
    return {**dict(chapter), "pages": [dict(p) for p in pages]}


@router.delete("/chapters/{chapter_id}", status_code=204)
def delete_chapter(chapter_id: int):
    with connect() as conn:
        if not conn.execute("DELETE FROM chapters WHERE id = ?", (chapter_id,)).rowcount:
            raise HTTPException(404, "Chapter not found")
    shutil.rmtree(LIBRARY_DIR / str(chapter_id), ignore_errors=True)


@router.get("/pages/{page_id}/image")
def get_page_image(page_id: int):
    with connect() as conn:
        row = conn.execute("SELECT chapter_id, filename FROM pages WHERE id = ?", (page_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Page not found")
    path = LIBRARY_DIR / str(row["chapter_id"]) / row["filename"]
    if not path.is_file():
        raise HTTPException(404, "Image file missing")
    return FileResponse(path, headers={"Cache-Control": "public, max-age=86400"})
