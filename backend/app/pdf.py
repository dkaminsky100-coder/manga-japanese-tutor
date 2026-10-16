"""PDF -> page images.

Scanned manga PDFs usually hold one full-page image per page; extracting that original
keeps full quality (and is much faster than rendering). Anything else - vector pages,
rotated pages, several images per page - is rendered at RENDER_DPI instead.
"""
from __future__ import annotations

import pymupdf

EXTRACTABLE = {"png", "jpeg", "jpg", "bmp", "gif", "webp"}
RENDER_DPI = 200
FULL_PAGE_COVERAGE = 0.8  # an embedded image covering this much of the page is "the page"
MARGINED_COVERAGE = 0.3  # ...or this much, if it is the only thing on the page
MAX_PAGES = 500


class PdfError(ValueError):
    pass


def _embedded_page_image(doc: pymupdf.Document, page: pymupdf.Page) -> tuple[str, bytes] | None:
    if page.rotation:
        return None
    images = page.get_images(full=True)
    if len(images) != 1:
        return None
    xref = images[0][0]
    rects = page.get_image_rects(xref)
    if len(rects) != 1:
        return None
    page_area = page.rect.width * page.rect.height
    if page_area <= 0:
        return None
    coverage = rects[0].width * rects[0].height / page_area
    if coverage < FULL_PAGE_COVERAGE:
        # Scans placed inside page margins (e.g. made in Word) cover less of the page; accept
        # them only when the image is the page's sole content.
        if coverage < MARGINED_COVERAGE or page.get_text().strip() or page.get_drawings():
            return None
    info = doc.extract_image(xref)
    if not info or info.get("ext", "").lower() not in EXTRACTABLE:
        return None
    return info["ext"].lower(), info["image"]


def extract_pdf_pages(data: bytes, stem: str) -> list[tuple[str, bytes]]:
    """Return [(filename, image_bytes)] for every page, in page order."""
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as e:  # noqa: BLE001 - pymupdf raises several error types for bad files
        raise PdfError(f"not a readable PDF ({e})") from e
    with doc:
        if doc.needs_pass:
            raise PdfError("PDF is password-protected")
        if doc.page_count > MAX_PAGES:
            raise PdfError(f"too many pages (max {MAX_PAGES})")
        pages: list[tuple[str, bytes]] = []
        for i, page in enumerate(doc, 1):
            embedded = _embedded_page_image(doc, page)
            if embedded:
                ext, img = embedded
            else:
                ext, img = "png", page.get_pixmap(dpi=RENDER_DPI).tobytes("png")
            pages.append((f"{stem}_p{i:04d}.{ext}", img))
        return pages
