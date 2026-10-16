import sqlite3
from contextlib import contextmanager
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
LIBRARY_DIR = DATA_DIR / "library"
DB_PATH = DATA_DIR / "app.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS chapters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    idx INTEGER NOT NULL,
    filename TEXT NOT NULL,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    UNIQUE (chapter_id, idx)
);
CREATE TABLE IF NOT EXISTS page_analysis (
    page_id INTEGER PRIMARY KEY REFERENCES pages(id) ON DELETE CASCADE,
    status TEXT NOT NULL,            -- pending | running | done | error
    error TEXT,
    detect_ms INTEGER,
    ocr_ms INTEGER,
    upscaled INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS blocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    page_id INTEGER NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    idx INTEGER NOT NULL,
    x1 INTEGER NOT NULL, y1 INTEGER NOT NULL, x2 INTEGER NOT NULL, y2 INTEGER NOT NULL,
    vertical INTEGER NOT NULL,
    conf REAL NOT NULL,
    text TEXT NOT NULL,
    UNIQUE (page_id, idx)
);
CREATE TABLE IF NOT EXISTS translations (
    text TEXT PRIMARY KEY,
    translation TEXT NOT NULL,
    model TEXT NOT NULL
);
"""


def init_db() -> None:
    LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.executescript(SCHEMA)


@contextmanager
def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
