import io
import sqlite3
import time

import pytest
from PIL import Image

from app import db
from app.nlp import translate as translator
from app.pipeline import runner
from app.pipeline.detect import TextBlock


def png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (100, 200), "white").save(buf, "PNG")
    return buf.getvalue()


def wait_done(client, page_id, timeout=5):
    end = time.time() + timeout
    while time.time() < end:
        a = client.get(f"/api/pages/{page_id}/analysis").json()
        if a["status"] in ("done", "error"):
            return a
        time.sleep(0.05)
    raise AssertionError("analysis did not finish")


class Reader:
    """Stand-in for detection + OCR whose output the test controls between page reads."""

    def __init__(self, monkeypatch):
        self.boxes = [(10, 10, 50, 90)]
        self.texts = ["こんにちは"]
        monkeypatch.setattr(runner, "detect_blocks", lambda img: [TextBlock(*b, True, 0.9) for b in self.boxes])
        monkeypatch.setattr(runner, "read_block", lambda rgb, b: self.texts[self.boxes.index(b.bbox)])


@pytest.fixture
def page(client, monkeypatch):
    reader = Reader(monkeypatch)
    cid = client.post("/api/chapters", files=[("files", ("a.png", png()))]).json()["id"]
    page_id = client.get(f"/api/chapters/{cid}").json()["pages"][0]["id"]
    return client, reader, page_id


def first_block(client, page_id):
    return wait_done(client, page_id)["blocks"][0]


def reread(client, page_id):
    """Mark the page as analysed by an old pipeline so the next request reads it again."""
    with db.connect() as conn:
        conn.execute("UPDATE page_analysis SET version = 0 WHERE page_id = ?", (page_id,))
    client.get(f"/api/pages/{page_id}/analysis")  # queues the re-read
    return wait_done(client, page_id)


def test_edit_updates_text_and_reanalyses(page):
    client, _, page_id = page
    block = first_block(client, page_id)
    assert block["edited"] is False and block["text"] == block["ocr_text"] == "こんにちは"

    r = client.patch(f"/api/blocks/{block['id']}", json={"text": "食べた"})
    assert r.status_code == 200
    edited = r.json()
    assert edited["text"] == "食べた" and edited["ocr_text"] == "こんにちは" and edited["edited"] is True
    # the response carries the fresh breakdown for the new text
    assert [t["surface"] for t in edited["tokens"]] == ["食べ", "た"]
    assert edited["grammar"][0]["summary"] == "past"
    # and the analysis endpoint now serves it too
    assert client.get(f"/api/pages/{page_id}/analysis").json()["blocks"][0]["text"] == "食べた"


def test_edit_cleans_whitespace_and_validates(page):
    client, _, page_id = page
    bid = first_block(client, page_id)["id"]
    assert client.patch(f"/api/blocks/{bid}", json={"text": " 食 べ\nた 　"}).json()["text"] == "食べた"
    assert client.patch(f"/api/blocks/{bid}", json={"text": "  \n "}).status_code == 400
    assert client.patch(f"/api/blocks/{bid}", json={"text": "あ" * 401}).status_code == 400
    assert client.patch(f"/api/blocks/{bid}", json={}).status_code == 422
    assert client.patch("/api/blocks/9999", json={"text": "あ"}).status_code == 404
    assert client.get(f"/api/pages/{page_id}/analysis").json()["blocks"][0]["text"] == "食べた"  # bad edits changed nothing


def test_editing_back_to_the_ocr_text_is_not_an_edit(page):
    client, _, page_id = page
    bid = first_block(client, page_id)["id"]
    client.patch(f"/api/blocks/{bid}", json={"text": "別の"})
    assert client.patch(f"/api/blocks/{bid}", json={"text": "こんにちは"}).json()["edited"] is False


def test_revert_restores_the_ocr_text(page):
    client, _, page_id = page
    bid = first_block(client, page_id)["id"]
    client.patch(f"/api/blocks/{bid}", json={"text": "食べた"})
    r = client.post(f"/api/blocks/{bid}/revert").json()
    assert r["text"] == "こんにちは" and r["edited"] is False and r["tokens"]
    assert client.post("/api/blocks/9999/revert").status_code == 404


def test_translation_uses_the_corrected_text(page, monkeypatch):
    client, _, page_id = page
    bid = first_block(client, page_id)["id"]
    seen = []
    monkeypatch.setattr(translator, "translate", lambda text: seen.append(text) or f"EN({text})")
    client.patch(f"/api/blocks/{bid}", json={"text": "食べた"})
    assert client.post(f"/api/blocks/{bid}/translate").json()["translation"] == "EN(食べた)"
    assert seen == ["食べた"]


def test_correction_survives_a_reread_even_if_the_ocr_text_changes(page):
    client, reader, page_id = page
    bid = first_block(client, page_id)["id"]
    client.patch(f"/api/blocks/{bid}", json={"text": "食べた"})

    reader.texts = ["こんばんは"]  # the improved pipeline now reads something else
    reader.boxes = [(12, 12, 52, 92)]  # ...and the box moved a little
    again = reread(client, page_id)
    (b,) = again["blocks"]
    assert b["text"] == "食べた" and b["edited"] is True  # the user's fix wins
    assert b["ocr_text"] == "こんばんは"  # but the new OCR reading is recorded
    assert b["bbox"] == [12, 12, 52, 92]
    assert client.post(f"/api/blocks/{b['id']}/revert").json()["text"] == "こんばんは"


def test_correction_survives_when_the_bubble_is_no_longer_detected(page):
    client, reader, page_id = page
    bid = first_block(client, page_id)["id"]
    client.patch(f"/api/blocks/{bid}", json={"text": "食べた"})

    reader.boxes, reader.texts = [(300, 300, 340, 380)], ["別の吹き出し"]  # elsewhere on the page
    again = reread(client, page_id)
    by_text = {b["text"]: b for b in again["blocks"]}
    assert by_text["食べた"]["edited"] is True and by_text["食べた"]["bbox"] == [10, 10, 50, 90]  # kept as it was
    assert by_text["別の吹き出し"]["edited"] is False  # the new block did not inherit it


def test_unedited_blocks_are_replaced_by_a_reread(page):
    client, reader, page_id = page
    first_block(client, page_id)
    reader.texts = ["新しい"]
    assert [b["text"] for b in reread(client, page_id)["blocks"]] == ["新しい"]


def test_old_database_gets_the_new_columns(tmp_path, monkeypatch):
    path = tmp_path / "old.sqlite"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE chapters (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE pages (id INTEGER PRIMARY KEY AUTOINCREMENT, chapter_id INTEGER NOT NULL, idx INTEGER NOT NULL,
            filename TEXT NOT NULL, width INTEGER NOT NULL, height INTEGER NOT NULL);
        CREATE TABLE page_analysis (page_id INTEGER PRIMARY KEY, status TEXT NOT NULL, error TEXT, detect_ms INTEGER,
            ocr_ms INTEGER, upscaled INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE blocks (id INTEGER PRIMARY KEY AUTOINCREMENT, page_id INTEGER NOT NULL, idx INTEGER NOT NULL,
            x1 INTEGER NOT NULL, y1 INTEGER NOT NULL, x2 INTEGER NOT NULL, y2 INTEGER NOT NULL,
            vertical INTEGER NOT NULL, conf REAL NOT NULL, text TEXT NOT NULL, UNIQUE (page_id, idx));
        INSERT INTO blocks (page_id, idx, x1, y1, x2, y2, vertical, conf, text) VALUES (1, 0, 0, 0, 5, 5, 1, 0.9, 'こんにちは');
        """
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(db, "DB_PATH", path)
    monkeypatch.setattr(db, "LIBRARY_DIR", tmp_path / "library")

    db.init_db()
    with db.connect() as c:
        row = c.execute("SELECT text, ocr_text, edited FROM blocks").fetchone()
        assert (row["text"], row["ocr_text"], row["edited"]) == ("こんにちは", "こんにちは", 0)
        assert {r["name"] for r in c.execute("PRAGMA table_info(page_analysis)")} >= {"version"}
    db.init_db()  # running it again is harmless
