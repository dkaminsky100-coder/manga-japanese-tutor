import io
import zipfile

from PIL import Image


def png(w=40, h=60) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), "white").save(buf, "PNG")
    return buf.getvalue()


def test_upload_images_natural_order(client):
    files = [("files", (n, png(), "image/png")) for n in ("p10.png", "p2.png", "p1.png")]
    r = client.post("/api/chapters", data={"title": "Ch1"}, files=files)
    assert r.status_code == 200 and r.json()["page_count"] == 3
    ch = client.get(f"/api/chapters/{r.json()['id']}").json()
    assert [p["idx"] for p in ch["pages"]] == [0, 1, 2]
    assert (ch["pages"][0]["width"], ch["pages"][0]["height"]) == (40, 60)
    img = client.get(f"/api/pages/{ch['pages'][0]['id']}/image")
    assert img.status_code == 200 and img.headers["content-type"].startswith("image/")


def test_upload_cbz(client):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("b/2.png", png())
        zf.writestr("b/1.png", png(10, 10))
        zf.writestr("b/notes.txt", "skip me")
    r = client.post("/api/chapters", files=[("files", ("vol.cbz", buf.getvalue()))])
    assert r.status_code == 200 and r.json()["page_count"] == 2
    assert r.json()["title"] == "vol"
    assert client.get(f"/api/chapters/{r.json()['id']}").json()["pages"][0]["width"] == 10


def test_rejects_bad_input(client):
    assert client.post("/api/chapters", files=[("files", ("a.txt", b"x"))]).status_code == 400
    assert client.post("/api/chapters", files=[("files", ("a.png", b"notimage"))]).status_code == 400
    assert client.get("/api/chapters/999").status_code == 404


def test_list_and_delete(client):
    cid = client.post("/api/chapters", files=[("files", ("a.png", png()))]).json()["id"]
    assert client.get("/api/chapters").json()[0]["page_count"] == 1
    assert client.delete(f"/api/chapters/{cid}").status_code == 204
    assert client.get("/api/chapters").json() == []
