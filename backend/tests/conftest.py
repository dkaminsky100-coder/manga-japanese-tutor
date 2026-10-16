import pytest
from fastapi.testclient import TestClient

from app import db


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "LIBRARY_DIR", tmp_path / "library")
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "app.sqlite")
    from app.routes import library

    monkeypatch.setattr(library, "LIBRARY_DIR", tmp_path / "library")
    from app.main import app

    with TestClient(app) as c:
        yield c
