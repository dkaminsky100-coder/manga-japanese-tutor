import pytest

from app.nlp.furigana import has_kanji, kata_to_hira, ruby_segments


@pytest.mark.parametrize(
    "surface, reading, expected",
    [
        # ruby only over kanji; okurigana untouched
        ("食べた", "タベタ", [("食", "た"), ("べた", None)]),
        ("取り出す", "トリダス", [("取", "と"), ("り", None), ("出", "だ"), ("す", None)]),
        ("お願い", "オネガイ", [("お", None), ("願", "ねが"), ("い", None)]),
        # kanji-only words get one ruby block
        ("連中", "レンチュウ", [("連中", "れんちゅう")]),
        ("大人", "オトナ", [("大人", "おとな")]),
        ("人々", "ヒトビト", [("人々", "ひとびと")]),
        # no kanji -> nothing to annotate
        ("エルフ", "エルフ", [("エルフ", None)]),
        ("ねえ", "ネエ", [("ねえ", None)]),
        ("！", "！", [("！", None)]),
    ],
)
def test_ruby_segments(surface, reading, expected):
    assert ruby_segments(surface, reading) == expected


def test_reading_may_be_hiragana_or_katakana():
    assert ruby_segments("食べた", "たべた") == ruby_segments("食べた", "タベタ")


def test_unalignable_reading_falls_back_to_whole_word():
    # okurigana in the surface (べ) isn't in the reading, so alignment is impossible
    assert ruby_segments("食べた", "ごはん") == [("食べた", "ごはん")]


def test_helpers():
    assert kata_to_hira("ラーメン") == "らーめん"  # long-vowel mark is kept
    assert has_kanji("a漢b") and not has_kanji("かな")
