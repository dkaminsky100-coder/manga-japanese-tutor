"""Turn a block of OCR text into tokens with furigana and dictionary entries."""
from __future__ import annotations

from functools import lru_cache

from ..dict.lookup import lookup
from .furigana import ruby_segments
from .tokenize import Token, tokenize

MAX_COMPOUND_TOKENS = 4


def _entries_for(t: Token) -> list[dict]:
    """Dictionary entries for a token, trying its base form, then Sudachi's normalized form."""
    # The token's reading only identifies the right homograph when the word is uninflected.
    reading = t.reading if t.surface == t.dictionary_form else None
    for form in dict.fromkeys([t.dictionary_form, t.normalized_form, t.surface]):
        entries = lookup(form, reading, pos=t.pos)
        if entries:
            return entries
    return []


def _find_compounds(tokens: list[Token]) -> list[dict]:
    """Greedy longest match of multi-token dictionary entries (e.g. 気 + を + つけろ -> 気をつける).

    The last token of a candidate is taken in its dictionary form so inflected endings still match.
    """
    compounds = []
    i = 0
    while i < len(tokens):
        found = None
        for n in range(min(MAX_COMPOUND_TOKENS, len(tokens) - i), 1, -1):
            span = tokens[i : i + n]
            if not all(t.is_word for t in span):
                continue
            candidate = "".join(t.surface for t in span[:-1]) + span[-1].dictionary_form
            entries = lookup(candidate)
            if entries:
                found = {"start": i, "end": i + n, "text": candidate, "entries": entries}
                break
        if found:
            compounds.append(found)
            i = found["end"]
        else:
            i += 1
    return compounds


def _token_json(t: Token, with_entries: bool = True) -> dict:
    out = {
        "surface": t.surface,
        "reading": t.reading,
        "dictionary_form": t.dictionary_form,
        "pos": t.pos,
        "pos_label": t.pos_label,
        "pos_detail": t.pos_detail,
        "conj_type": t.conj_type,
        "conj_form": t.conj_form,
        "ruby": [{"text": text, "ruby": ruby} for text, ruby in ruby_segments(t.surface, t.reading)],
    }
    if with_entries:
        out["entries"] = _entries_for(t) if t.is_word else []
        out["parts"] = [_token_json(p, with_entries=False) for p in t.parts]
    return out


@lru_cache(maxsize=512)
def analyze_text(text: str) -> dict:
    tokens = tokenize(text)
    return {"tokens": [_token_json(t) for t in tokens], "compounds": _find_compounds(tokens)}
