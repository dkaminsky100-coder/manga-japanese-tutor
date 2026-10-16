import io
import time

from PIL import Image

from app.nlp import translate as translator
from app.pipeline import runner
from app.pipeline.detect import TextBlock


def make_block(client, monkeypatch, text="どうしようもねえよ"):
    """Upload a page and run (stubbed) analysis so a block row exists; return its id."""
    monkeypatch.setattr(runner, "detect_blocks", lambda img: [TextBlock(1, 1, 20, 40, True, 0.9)])
    monkeypatch.setattr(runner, "read_block", lambda rgb, b: text)
    buf = io.BytesIO()
    Image.new("RGB", (50, 80), "white").save(buf, "PNG")
    cid = client.post("/api/chapters", files=[("files", ("a.png", buf.getvalue()))]).json()["id"]
    page_id = client.get(f"/api/chapters/{cid}").json()["pages"][0]["id"]
    end = time.time() + 5
    while time.time() < end:
        a = client.get(f"/api/pages/{page_id}/analysis").json()
        if a["status"] == "done":
            return a["blocks"][0]["id"]
        time.sleep(0.05)
    raise AssertionError("analysis did not finish")


def test_translate_returns_and_caches(client, monkeypatch):
    block_id = make_block(client, monkeypatch)
    calls = []
    monkeypatch.setattr(translator, "translate", lambda text: calls.append(text) or "I can't help it.")

    first = client.post(f"/api/blocks/{block_id}/translate").json()
    assert first == {"translation": "I can't help it.", "model": translator.MODEL_NAME, "cached": False}

    second = client.post(f"/api/blocks/{block_id}/translate").json()
    assert second["translation"] == "I can't help it." and second["cached"] is True
    assert calls == ["どうしようもねえよ"]  # the model ran only once


def test_translate_unknown_block_is_404(client):
    assert client.post("/api/blocks/999/translate").status_code == 404


def test_translate_model_failure_is_503_and_not_cached(client, monkeypatch):
    block_id = make_block(client, monkeypatch)

    def boom(text):
        raise RuntimeError("download failed")

    monkeypatch.setattr(translator, "translate", boom)
    r = client.post(f"/api/blocks/{block_id}/translate")
    assert r.status_code == 503 and "download failed" in r.json()["detail"]

    monkeypatch.setattr(translator, "translate", lambda text: "ok")  # retry succeeds, nothing stale cached
    assert client.post(f"/api/blocks/{block_id}/translate").json()["translation"] == "ok"


def test_translate_empty_text_helper():
    assert translator.translate("   ") == ""  # no model load for blank input
