import io
import time

from PIL import Image

from app.pipeline import runner
from app.pipeline.detect import TextBlock, decode_blocks
import numpy as np


def png(w=100, h=200) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), "white").save(buf, "PNG")
    return buf.getvalue()


def wait_done(client, page_id, timeout=5):
    end = time.time() + timeout
    while time.time() < end:
        a = client.get(f"/api/pages/{page_id}/analysis").json()
        if a["status"] in ("done", "error"):
            return a
        time.sleep(0.05)
    raise AssertionError("analysis did not finish")


def upload(client, n):
    files = [("files", (f"{i}.png", png(), "image/png")) for i in range(n)]
    cid = client.post("/api/chapters", files=files).json()["id"]
    return client.get(f"/api/chapters/{cid}").json()["pages"]


def test_analysis_runs_and_stores_blocks(client, monkeypatch):
    monkeypatch.setattr(runner, "detect_blocks", lambda img: [
        TextBlock(10, 20, 40, 90, True, 0.9),
        TextBlock(50, 60, 80, 100, True, 0.8),
    ])
    monkeypatch.setattr(runner, "read_block", lambda rgb, b: "こんにちは" if b.x1 == 10 else "")
    pages = upload(client, 1)

    a = wait_done(client, pages[0]["id"])
    assert a["status"] == "done"
    # the block with empty OCR text is dropped
    assert [b["text"] for b in a["blocks"]] == ["こんにちは"]
    assert a["blocks"][0]["bbox"] == [10, 20, 40, 90]
    assert a["upscaled"] is False


def test_analysis_prefetches_following_pages(client, monkeypatch):
    monkeypatch.setattr(runner, "detect_blocks", lambda img: [])
    monkeypatch.setattr(runner, "read_block", lambda rgb, b: "x")
    pages = upload(client, 4)

    wait_done(client, pages[0]["id"])
    # opening page 0 queues pages 1 and 2 but not 3
    assert wait_done(client, pages[1]["id"])["status"] == "done"
    assert wait_done(client, pages[2]["id"])["status"] == "done"
    assert client.get(f"/api/pages/{pages[3]['id']}/analysis").json()["status"] in ("pending", "running", "done")


def test_analysis_error_is_reported(client, monkeypatch):
    def boom(img):
        raise RuntimeError("model exploded")

    monkeypatch.setattr(runner, "detect_blocks", boom)
    pages = upload(client, 1)
    a = wait_done(client, pages[0]["id"])
    assert a["status"] == "error" and "model exploded" in a["error"]


def test_unknown_page_404(client):
    assert client.get("/api/pages/999/analysis").status_code == 404


def test_decode_blocks_scales_and_nms():
    # two overlapping candidates for one block + one low-confidence candidate, scale 0.5
    pred = np.array([
        [100, 100, 40, 80, 0.95, 0.9, 0.1],
        [102, 101, 40, 80, 0.90, 0.9, 0.1],
        [300, 300, 40, 40, 0.20, 0.5, 0.5],
    ], dtype=np.float32)
    blocks = decode_blocks(pred, scale=0.5, img_w=1000, img_h=1000)
    assert len(blocks) == 1
    b = blocks[0]
    assert (b.x1, b.y1, b.x2, b.y2) == (160, 120, 240, 280)
    assert b.vertical


def test_pages_analysed_by_an_older_pipeline_are_read_again(client, monkeypatch):
    from app import db

    reads = []
    monkeypatch.setattr(runner, "detect_blocks", lambda img: [TextBlock(1, 1, 20, 40, True, 0.9)])
    monkeypatch.setattr(runner, "read_block", lambda rgb, b: reads.append(1) or f"text{len(reads)}")
    pages = upload(client, 1)
    pid = pages[0]["id"]

    first = wait_done(client, pid)
    assert first["blocks"][0]["text"] == "text1" and len(reads) == 1
    assert client.get(f"/api/pages/{pid}/analysis").json()["status"] == "done"  # current version: left alone
    assert len(reads) == 1

    with db.connect() as conn:  # pretend an older pipeline produced it
        conn.execute("UPDATE page_analysis SET version = 0 WHERE page_id = ?", (pid,))
    assert client.get(f"/api/pages/{pid}/analysis").json()["status"] in ("pending", "running", "done")
    again = wait_done(client, pid)
    assert again["blocks"][0]["text"] == "text2" and len(reads) == 2
    with db.connect() as conn:
        assert conn.execute("SELECT version FROM page_analysis WHERE page_id = ?", (pid,)).fetchone()[0] == runner.PIPELINE_VERSION
