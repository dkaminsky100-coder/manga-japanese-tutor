"""Japanese morphological analysis with SudachiPy (full dictionary)."""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

from sudachipy import dictionary, tokenizer

from .furigana import kata_to_hira

# Sudachi's top-level part of speech -> short English label.
POS_LABELS = {
    "名詞": "noun",
    "代名詞": "pronoun",
    "動詞": "verb",
    "形容詞": "i-adjective",
    "形状詞": "na-adjective",
    "副詞": "adverb",
    "助詞": "particle",
    "助動詞": "auxiliary verb",
    "接続詞": "conjunction",
    "連体詞": "adnominal",
    "感動詞": "interjection",
    "接頭辞": "prefix",
    "接尾辞": "suffix",
    "補助記号": "symbol",
    "記号": "symbol",
    "空白": "space",
}
NON_WORD_POS = {"補助記号", "記号", "空白"}


@dataclass
class Token:
    surface: str
    dictionary_form: str
    normalized_form: str
    reading: str  # hiragana
    pos: str  # Sudachi top-level POS, e.g. 動詞
    pos_detail: str
    conj_type: str  # e.g. 下一段-バ行, or "" if uninflected
    conj_form: str  # e.g. 連用形-一般, or ""
    start: int
    end: int
    parts: list["Token"] = field(default_factory=list)  # finer split (mode A) when it differs

    @property
    def pos_label(self) -> str:
        return POS_LABELS.get(self.pos, self.pos)

    @property
    def is_word(self) -> bool:
        return self.pos not in NON_WORD_POS


@lru_cache(maxsize=1)
def _tokenizer():
    return dictionary.Dictionary(dict="full").tokenizer()


def _clean(value: str) -> str:
    return "" if value == "*" else value


def _token(m, parts: list[Token] | None = None) -> Token:
    pos = m.part_of_speech()
    reading = kata_to_hira(m.reading_form())
    return Token(
        surface=m.surface(),
        dictionary_form=m.dictionary_form(),
        normalized_form=m.normalized_form(),
        # Sudachi leaves unknown words (and punctuation) with an empty or echoed reading.
        reading=reading if reading else m.surface(),
        pos=pos[0],
        pos_detail=_clean(pos[1]),
        conj_type=_clean(pos[4]),
        conj_form=_clean(pos[5]),
        start=m.begin(),
        end=m.end(),
        parts=parts or [],
    )


def tokenize(text: str) -> list[Token]:
    """Split text into words (Sudachi mode C: longest units, e.g. 連中, 領主)."""
    tok = _tokenizer()
    out = []
    for m in tok.tokenize(text, tokenizer.Tokenizer.SplitMode.C):
        fine = m.split(tokenizer.Tokenizer.SplitMode.A)
        parts = [_token(p) for p in fine] if len(fine) > 1 else []
        out.append(_token(m, parts))
    return out
