import pytest

from app.nlp.grammar import conj_label, find_units, particle_kind, particle_note, verb_class
from app.nlp.tokenize import tokenize


def summaries(text: str) -> list[tuple[str, str]]:
    return [(u["text"], u["summary"]) for u in find_units(tokenize(text))]


@pytest.mark.parametrize(
    "text, expected",
    [
        ("食べさせられた", [("食べさせられた", "causative → passive → past")]),
        ("食べられない", [("食べられない", "passive / potential → negative")]),
        ("食べている", [("食べている", "ongoing / resulting state")]),
        ("食べちゃった", [("食べちゃった", "completed / regret → past")]),
        ("食べたくなかった", [("食べたくなかった", "want to → negative past")]),
        ("行きませんでした", [("行きませんでした", "polite negative past")]),
        ("読んでください", [("読んでください", "please")]),
        ("見てみる", [("見てみる", "try doing")]),
        ("帰ってしまった", [("帰ってしまった", "completed / regret → past")]),
        ("食べさせてあげたい", [("食べさせてあげたい", "causative → do for someone → want to")]),
        ("食べれば", [("食べれば", "conditional")]),
        ("食べたら", [("食べたら", "conditional")]),
        ("食べなきゃ", [("食べなきゃ", "must (contracted)")]),
        ("食べないで", [("食べないで", "without / please don't")]),
        ("静かだった", [("静かだった", "past")]),
        ("学生じゃない", [("学生じゃない", "copula (contracted) → negative")]),
        ("美しくなかった", [("美しくなかった", "negative past")]),
        ("食べるでしょう", [("食べるでしょう", "probably")]),
        ("寝てた", [("寝てた", "ongoing state → past")]),
        # rough / manga speech
        ("動くんじゃねえ", [("動くんじゃねえ", "emphatic prohibition")]),
        ("ほどきやがれ", [("ほどきやがれ", "derogatory")]),
        ("手が出せねえんだ", [("出せねえんだ", "negative → explanatory")]),
        ("誰だあ", [("誰だあ", "copula")]),  # stretched だあ is explained as だ; the text keeps the あ
        ("かわいそうにあのエルフ", [("かわいそうに", "adverbial")]),
        ("静かな人", [("静かな", "attributive")]),
        ("静かで安全", [("静かで", "copula (te-form)")]),
    ],
)
def test_chain_summaries(text, expected):
    assert summaries(text) == expected


def test_noun_does_not_take_a_past_ending():
    # Sudachi reads this OCR string as pronoun なあん + た; "noun + past" must not become a chain
    assert summaries("コカ城の盗賊だなあんた？") == [("盗賊だ", "copula")]


def test_no_chain_for_plain_words():
    assert summaries("気をつけろ") == []  # verb alone, nothing attached
    assert summaries("ちょっと店") == []
    assert summaries("コカ城の連中には") == []


def test_unit_structure_and_token_range():
    tokens = tokenize("食べさせられた")
    (u,) = find_units(tokens)
    assert (u["start"], u["end"]) == (0, len(tokens)) and u["base"] == "食べる"
    head, *rest = u["steps"]
    assert head["text"] == "食べ" and head["label"].startswith("食べる — continuative stem")
    assert [s["text"] for s in rest] == ["させ", "られ", "た"]
    assert all(s["note"] for s in rest)  # every step is explained
    assert "key" not in head  # internal field not leaked to the API


def test_unit_range_inside_a_longer_sentence():
    tokens = tokenize("手が出せねえんだ")
    (u,) = find_units(tokens)
    assert "".join(t.surface for t in tokens[u["start"] : u["end"]]) == u["text"] == "出せねえんだ"


def test_multiple_units_in_one_sentence():
    us = summaries("食べたいけど行けない")
    assert [t for t, _ in us] == ["食べたい", "行けない"]


def test_imperative_aux_is_flagged():
    (u,) = find_units(tokenize("ほどきやがれ"))
    assert "imperative" in u["steps"][-1]["note"]


def test_passive_after_causative_is_just_passive():
    (u,) = find_units(tokenize("食べさせられる"))
    assert u["summary"] == "causative → passive"
    (u,) = find_units(tokenize("食べられる"))
    assert u["summary"] == "passive / potential"


def test_conjugation_labels():
    taberu, ta = tokenize("食べた")
    assert conj_label(taberu) == "continuative stem (before ます / た / て)"
    assert verb_class(taberu) == "ichidan verb"
    (kaite, _te) = tokenize("書いて")
    assert conj_label(kaite) == "te/ta stem (sound-changed continuative)"
    assert verb_class(kaite) == "godan verb"
    assert verb_class(ta) == ""  # auxiliaries aren't classed as verbs
    (utsukushiku, *_) = tokenize("美しくなかった")
    assert conj_label(utsukushiku) == "adverbial form (〜く)"
    assert tokenize("食べる")[0].conj_form and conj_label(tokenize("食べる")[0]) == "plain form"


def test_particle_notes():
    wa = next(t for t in tokenize("私は") if t.surface == "は")
    assert particle_note(wa) == "marks the topic of the sentence"
    assert particle_kind(wa) == "topic / focus particle"
    assert particle_note(tokenize("食べた")[0]) == ""  # not a particle
