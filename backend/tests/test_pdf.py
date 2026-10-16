import io

import pymupdf
import pytest
from PIL import Image

from app.pdf import PdfError, extract_pdf_pages


def jpeg(w, h) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), "white").save(buf, "JPEG")
    return buf.getvalue()


def make_pdf(builders) -> bytes:
    doc = pymupdf.open()
    for build in builders:
        page = doc.new_page(width=612, height=792)
        build(page)
    return doc.tobytes()


def scanned(page):
    page.insert_image(page.rect, stream=jpeg(300, 450))


def text_only(page):
    page.insert_text((72, 72), "hello")


def small_image(page):
    page.insert_image(pymupdf.Rect(0, 0, 100, 100), stream=jpeg(50, 50))


def test_scanned_page_keeps_original_image():
    pages = extract_pdf_pages(make_pdf([scanned]), "vol")
    assert [n for n, _ in pages] == ["vol_p0001.jpeg"]
    with Image.open(io.BytesIO(pages[0][1])) as im:
        assert im.size == (300, 450)  # native resolution, not re-rendered at page size


def margined(page):  # like a scan dropped into a Word page: 1-inch margins, nothing else
    page.insert_image(pymupdf.Rect(72, 72, 540, 720), stream=jpeg(470, 650))


def margined_with_text(page):
    margined(page)
    page.insert_text((72, 40), "caption")


def test_scan_inside_margins_keeps_original_image():
    pages = extract_pdf_pages(make_pdf([margined]), "w")
    assert pages[0][0] == "w_p0001.jpeg"
    with Image.open(io.BytesIO(pages[0][1])) as im:
        assert im.size == (470, 650)


def test_margined_image_with_other_content_is_rendered():
    pages = extract_pdf_pages(make_pdf([margined_with_text]), "w")
    assert pages[0][0] == "w_p0001.png"


def test_non_scanned_pages_are_rendered():
    pages = extract_pdf_pages(make_pdf([text_only, small_image]), "vol")
    assert [n for n, _ in pages] == ["vol_p0001.png", "vol_p0002.png"]
    with Image.open(io.BytesIO(pages[0][1])) as im:
        assert im.size == (round(612 / 72 * 200), round(792 / 72 * 200))  # 200 dpi


def test_mixed_pdf_preserves_page_order():
    pages = extract_pdf_pages(make_pdf([scanned, text_only, scanned]), "m")
    assert [n.split(".")[0] for n, _ in pages] == ["m_p0001", "m_p0002", "m_p0003"]


def test_bad_pdf_raises():
    with pytest.raises(PdfError):
        extract_pdf_pages(b"not a pdf", "x")


def test_upload_pdf_via_api(client):
    r = client.post("/api/chapters", files=[("files", ("scan.pdf", make_pdf([scanned, scanned])))])
    assert r.status_code == 200 and r.json()["page_count"] == 2 and r.json()["title"] == "scan"
    assert client.get(f"/api/chapters/{r.json()['id']}").json()["pages"][0]["width"] == 300


def test_upload_corrupt_pdf_is_400(client):
    r = client.post("/api/chapters", files=[("files", ("bad.pdf", b"%PDF-1.7 garbage"))])
    assert r.status_code == 400
