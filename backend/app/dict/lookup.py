"""JMdict lookups against the SQLite file built by import_jmdict."""
from __future__ import annotations

import json
import logging
import re
import sqlite3
import threading
from functools import lru_cache
from pathlib import Path

from .. import db

log = logging.getLogger(__name__)

MAX_SENSES = 6  # keep tooltips short; very common words (e.g. する) have dozens of senses

_local = threading.local()
_warned_missing = False


def dict_path() -> Path:
    return db.DATA_DIR / "dict.sqlite"


def _conn() -> sqlite3.Connection | None:
    global _warned_missing
    path = dict_path()
    cached = getattr(_local, "conn", None)
    if cached is not None and getattr(_local, "path", None) == path:
        return cached
    if not path.is_file():
        if not _warned_missing:
            log.warning("Dictionary not found at %s; run `python -m app.dict.import_jmdict <json>`", path)
            _warned_missing = True
        return None
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    _local.conn, _local.path = conn, path
    return conn


_ROMAJI_SUFFIX = re.compile(r"\s*\([a-z]+\)$")  # JMdict appends e.g. "(futsuumeishi)" to some tags


@lru_cache(maxsize=1)
def _tags(path: Path) -> dict[str, str]:
    conn = _conn()
    if conn is None:
        return {}
    return {r["code"]: _ROMAJI_SUFFIX.sub("", r["description"]) for r in conn.execute("SELECT code, description FROM tags")}


def _hira(s: str) -> str:
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)


# Sudachi top-level POS -> JMdict part-of-speech code prefixes that are compatible with it.
POS_TO_JMDICT = {
    "助詞": ("prt",),
    "助動詞": ("aux", "cop"),
    "動詞": ("v",),
    "形容詞": ("adj",),
    "形状詞": ("adj",),
    "名詞": ("n",),
    "代名詞": ("pn",),
    "副詞": ("adv",),
    "接続詞": ("conj",),
    "連体詞": ("adj-pn",),
    "感動詞": ("int",),
    "接頭辞": ("pref",),
    "接尾辞": ("suf", "n-suf", "ctr"),
}


def _pos_matches(senses: list[dict], sudachi_pos: str | None) -> bool:
    prefixes = POS_TO_JMDICT.get(sudachi_pos or "")
    return bool(prefixes) and any(p.startswith(prefixes) for s in senses for p in s["pos"])


def lookup(form: str, reading: str | None = None, limit: int = 3, pos: str | None = None) -> list[dict]:
    """Entries whose kanji or kana form is exactly `form`.

    Ranked: entries whose kana matches `reading` first (to pick 生きる/いきる over a homograph),
    then entries whose part of speech fits `pos` (Sudachi's, e.g. 助詞 so に is the particle and
    not 荷), then common words, then JMdict order. Returns [] if the dictionary isn't installed.
    """
    conn = _conn()
    if conn is None or not form:
        return []
    rows = conn.execute(
        """SELECT DISTINCT e.id, e.common, e.kanji, e.kana, e.senses
           FROM forms f JOIN entries e ON e.id = f.entry_id WHERE f.text = ?""",
        (form,),
    ).fetchall()
    reading = _hira(reading) if reading else None

    def rank(r: sqlite3.Row):
        kana = [_hira(k) for k in json.loads(r["kana"])]
        return (
            0 if reading and reading in kana else 1,
            0 if pos and _pos_matches(json.loads(r["senses"]), pos) else 1,
            0 if r["common"] else 1,
            r["id"],
        )

    prefixes = POS_TO_JMDICT.get(pos or "")
    tags = _tags(dict_path())
    out = []
    for r in sorted(rows, key=rank)[:limit]:
        senses = json.loads(r["senses"])
        if prefixes:
            # Show the senses that fit this usage first (ない as an auxiliary, not "nonexistent").
            senses.sort(key=lambda s: not any(p.startswith(prefixes) for p in s["pos"]))  # stable
        out.append(
            {
                "id": r["id"],
                "common": bool(r["common"]),
                "kanji": json.loads(r["kanji"]),
                "kana": json.loads(r["kana"]),
                "senses": [
                    {
                        "pos": [tags.get(p, p) for p in s["pos"]],
                        "glosses": s["gloss"],
                        "misc": [tags.get(m, m) for m in s["misc"]],
                    }
                    for s in senses[:MAX_SENSES]
                ],
                "more_senses": max(0, len(senses) - MAX_SENSES),
            }
        )
    return out
