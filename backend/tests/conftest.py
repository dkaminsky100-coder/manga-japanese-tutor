import pytest
from fastapi.testclient import TestClient

# Importing the app runs load_dotenv(), so import it before the fixture clears env vars.
from app import db
from app.main import app
from app.pipeline import runner
from app.routes import library


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.delenv("WAIFU2X_EXE", raising=False)  # never upscale in tests, whatever backend/.env says
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "LIBRARY_DIR", tmp_path / "library")
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "app.sqlite")
    monkeypatch.setattr(library, "LIBRARY_DIR", tmp_path / "library")
    monkeypatch.setattr(runner, "warm_up", lambda: None)  # don't load real models in tests

    with TestClient(app) as c:
        yield c
