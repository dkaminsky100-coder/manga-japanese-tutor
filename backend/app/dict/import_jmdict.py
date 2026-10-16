"""One-time import of JMdict (jmdict-simplified JSON, English glosses) into SQLite.

    python -m app.dict.import_jmdict path/to/jmdict-eng-3.x.json [--out data/dict.sqlite]

Get the JSON from https://github.com/scriptin/jmdict-simplified/releases (the plain
`jmdict-eng-*.json.zip`, not the "common" subset). JMdict is (c) the Electronic Dictionary
Research and Development Group, used under CC BY-SA 4.0.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from ..db import DATA_DIR

DICT_PATH = DATA_DIR / "dict.sqlite"

SCHEMA = """
CREATE TABLE entries (
    id INTEGER PRIMARY KEY,   -- JMdict ent_seq
    common INTEGER NOT NULL,  -- 1 if any form is flagged common (news1/ichi1/spec1/gai1...)
    kanji TEXT NOT NULL,      -- JSON list of kanji forms
    kana TEXT NOT NULL,       -- JSON list of kana forms
    senses TEXT NOT NULL      -- JSON list of {pos, gloss, misc, field}
);
CREATE TABLE forms (
    text TEXT NOT NULL,
    entry_id INTEGER NOT NULL REFERENCES entries(id),
    common INTEGER NOT NULL
);
CREATE INDEX forms_text ON forms(text);
CREATE TABLE tags (code TEXT PRIMARY KEY, description TEXT NOT NULL);
"""


def import_jmdict(json_path: Path, out_path: Path = DICT_PATH) -> int:
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    conn = sqlite3.connect(tmp)
    conn.executescript(SCHEMA)

    conn.executemany("INSERT INTO tags VALUES (?, ?)", data["tags"].items())

    entries, forms = [], []
    for w in data["words"]:
        eid = int(w["id"])
        kanji = [k["text"] for k in w.get("kanji", [])]
        kana = [k["text"] for k in w.get("kana", [])]
        common = int(any(k.get("common") for k in w.get("kanji", []) + w.get("kana", [])))
        senses = [
            {
                "pos": s.get("partOfSpeech", []),
                "gloss": [g["text"] for g in s.get("gloss", [])],
                "misc": s.get("misc", []),
                "field": s.get("field", []),
            }
            for s in w.get("sense", [])
        ]
        entries.append((eid, common, json.dumps(kanji, ensure_ascii=False),
                        json.dumps(kana, ensure_ascii=False), json.dumps(senses, ensure_ascii=False)))
        for k in w.get("kanji", []):
            forms.append((k["text"], eid, int(bool(k.get("common")))))
        for k in w.get("kana", []):
            forms.append((k["text"], eid, int(bool(k.get("common")))))

    conn.executemany("INSERT INTO entries VALUES (?,?,?,?,?)", entries)
    conn.executemany("INSERT INTO forms VALUES (?,?,?)", forms)
    conn.commit()
    conn.close()
    tmp.replace(out_path)
    return len(entries)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("json_path", type=Path)
    ap.add_argument("--out", type=Path, default=DICT_PATH)
    args = ap.parse_args()
    n = import_jmdict(args.json_path, args.out)
    print(f"Imported {n} entries into {args.out}")
