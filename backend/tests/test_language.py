"""Dictionary import/lookup and text analysis, using a tiny hand-made JMdict file."""
import json

import pytest

from app import db
from app.dict import lookup as lookup_mod
from app.dict.import_jmdict import import_jmdict
from app.nlp import analyze as analyze_mod

TAGS = {
    "prt": "particle",
    "n": "noun (common) (futsuumeishi)",
    "v1": "Ichidan verb",
    "vt": "transitive verb",
    "exp": "expressions (phrases, clauses, etc.)",
}


def word(id_, kanji, kana, pos, glosses, common=True):
    return {
        "id": str(id_),
        "kanji": [{"common": common, "text": k, "tags": []} for k in kanji],
        "kana": [{"common": common, "text": k, "tags": [], "appliesToKanji": ["*"]} for k in kana],
        "sense": [{"partOfSpeech": pos, "gloss": [{"lang": "eng", "text": g} for g in glosses], "misc": [], "field": []}],
    }


WORDS = [
    # 荷 sorts before the particle に in JMdict order and is common, like the real dictionary
    word(1, ["荷"], ["に"], ["n"], ["load", "baggage"]),
    word(2, [], ["に"], ["prt"], ["at", "in"]),
    word(3, ["食べる"], ["たべる"], ["v1", "vt"], ["to eat"]),
    word(4, ["気をつける"], ["きをつける"], ["exp", "v1"], ["to be careful"]),
    word(5, ["気"], ["き"], ["n"], ["spirit"]),
    word(6, ["生きる"], ["いきる"], ["v1"], ["to live"]),
    word(7, ["生きる"], ["ikiru-other"], ["v1"], ["homograph with another reading"], common=False),
    # one entry, two usages: the adjective sense is listed first, like the real ない
    {**word(8, [], ["ない"], ["adj-i"], ["nonexistent"]),
     "sense": [
         {"partOfSpeech": ["adj-i"], "gloss": [{"lang": "eng", "text": "nonexistent"}], "misc": [], "field": []},
         {"partOfSpeech": ["aux-adj"], "gloss": [{"lang": "eng", "text": "not (negative)"}], "misc": [], "field": []},
     ]},
]


@pytest.fixture
def dictionary(tmp_path, monkeypatch):
    src = tmp_path / "jmdict.json"
    src.write_text(json.dumps({"tags": TAGS, "words": WORDS}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    assert import_jmdict(src, tmp_path / "dict.sqlite") == len(WORDS)
    # drop per-thread connection / tag cache so each test sees its own file
    monkeypatch.setattr(lookup_mod, "_local", type(lookup_mod._local)())
    lookup_mod._tags.cache_clear()
    analyze_mod.analyze_text.cache_clear()
    yield tmp_path
    lookup_mod._tags.cache_clear()
    analyze_mod.analyze_text.cache_clear()


def test_lookup_by_kanji_and_kana(dictionary):
    assert lookup_mod.lookup("食べる")[0]["senses"][0]["glosses"] == ["to eat"]
    assert lookup_mod.lookup("たべる")[0]["kanji"] == ["食べる"]
    assert lookup_mod.lookup("存在しない") == []


def test_pos_ranking_prefers_the_particle(dictionary):
    assert lookup_mod.lookup("に")[0]["senses"][0]["glosses"] == ["load", "baggage"]  # no hint: common noun first
    assert lookup_mod.lookup("に", pos="助詞")[0]["senses"][0]["glosses"] == ["at", "in"]
    assert lookup_mod.lookup("に", pos="名詞")[0]["senses"][0]["glosses"] == ["load", "baggage"]


def test_senses_matching_the_pos_are_listed_first(dictionary):
    def first_gloss(**kw):
        return lookup_mod.lookup("ない", **kw)[0]["senses"][0]["glosses"]

    assert first_gloss() == ["nonexistent"]  # JMdict order when we know nothing
    assert first_gloss(pos="助動詞") == ["not (negative)"]  # auxiliary usage
    assert first_gloss(pos="形容詞") == ["nonexistent"]


def test_reading_ranking_picks_the_right_homograph(dictionary):
    assert lookup_mod.lookup("生きる", reading="イキル")[0]["id"] == 6
    assert lookup_mod.lookup("生きる", reading="ikiru-other")[0]["id"] == 7


def test_pos_descriptions_are_resolved_and_cleaned(dictionary):
    senses = lookup_mod.lookup("食べる")[0]["senses"][0]
    assert senses["pos"] == ["Ichidan verb", "transitive verb"]
    assert lookup_mod.lookup("気")[0]["senses"][0]["pos"] == ["noun (common)"]  # romaji suffix stripped


def test_missing_dictionary_returns_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(lookup_mod, "_local", type(lookup_mod._local)())
    assert lookup_mod.lookup("食べる") == []


def test_analyze_tokens_ruby_and_entries(dictionary):
    a = analyze_mod.analyze_text("食べた")
    assert [t["surface"] for t in a["tokens"]] == ["食べ", "た"]
    first = a["tokens"][0]
    assert first["dictionary_form"] == "食べる" and first["pos_label"] == "verb"
    assert first["ruby"] == [{"text": "食", "ruby": "た"}, {"text": "べ", "ruby": None}]
    assert first["entries"][0]["senses"][0]["glosses"] == ["to eat"]


def test_analyze_particle_gets_particle_entry(dictionary):
    a = analyze_mod.analyze_text("気に")
    ni = next(t for t in a["tokens"] if t["surface"] == "に")
    assert ni["entries"][0]["senses"][0]["glosses"] == ["at", "in"]


def test_analyze_finds_multi_token_compound(dictionary):
    a = analyze_mod.analyze_text("気をつけろ")
    assert [t["surface"] for t in a["tokens"]] == ["気", "を", "つけろ"]
    (c,) = a["compounds"]
    assert (c["text"], c["start"], c["end"]) == ("気をつける", 0, 3)
    assert c["entries"][0]["senses"][0]["glosses"] == ["to be careful"]


def test_analyze_punctuation_gets_no_entries(dictionary):
    a = analyze_mod.analyze_text("気！！")
    bang = [t for t in a["tokens"] if t["pos"] == "補助記号"]
    assert bang and all(t["entries"] == [] for t in bang)
