"""Furigana: align a word's kana reading to its kanji.

`ruby_segments("食べた", "たべた")` -> [("食", "た"), ("べた", None)]: ruby goes over the kanji
runs only, never over the okurigana that is already written in kana.
"""
from __future__ import annotations

import re

_KANJI = "一-鿿㐀-䶿々〻"  # CJK ideographs, plus 々 and 〻 which repeat a kanji
_KANJI_RUN = re.compile(f"[{_KANJI}]+")


def kata_to_hira(s: str) -> str:
    """Katakana -> hiragana (the long-vowel mark ー and everything else are left alone)."""
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)


def has_kanji(s: str) -> bool:
    return _KANJI_RUN.search(s) is not None


def ruby_segments(surface: str, reading: str) -> list[tuple[str, str | None]]:
    """Split `surface` into (text, ruby) pieces; ruby is None for text that needs none.

    `reading` may be katakana or hiragana. If the reading can't be aligned to the kana inside
    the surface (irregular readings like 大人 -> おとな are fine, but a mismatched reading
    isn't), the whole surface gets the whole reading as one ruby block.
    """
    if not has_kanji(surface):
        return [(surface, None)]
    reading = kata_to_hira(reading)

    # Build ^(.+?)okurigana(.+?)...$ : each kanji run becomes a lazy capture, kana stay literal.
    pieces = []  # (is_kanji_run, text)
    pos = 0
    for m in _KANJI_RUN.finditer(surface):
        if m.start() > pos:
            pieces.append((False, surface[pos : m.start()]))
        pieces.append((True, m.group()))
        pos = m.end()
    if pos < len(surface):
        pieces.append((False, surface[pos:]))

    pattern = "".join("(.+?)" if is_kanji else re.escape(kata_to_hira(text)) for is_kanji, text in pieces)
    match = re.fullmatch(pattern, reading)
    if not match:
        return [(surface, reading)]

    groups = iter(match.groups())
    return [(text, next(groups) if is_kanji else None) for is_kanji, text in pieces]
