"""Rule-based grammar breakdown on top of Sudachi tokens.

Finds *predicate chains* - a verb, adjective or noun+copula plus the auxiliaries and
conjunctive particles attached to it (食べ + させ + られ + た) - and explains each step in
English ("causative -> passive -> past"). Also gives plain-English notes for particles and
conjugation forms. Everything here is a lookup table; no models, no network.
"""
from __future__ import annotations

from .tokenize import Token

# --------------------------------------------------------------------------- conjugation forms

_FORM_LABELS = {
    "未然形": "irrealis stem (before ない / れる / せる)",
    "連用形": "continuative stem (before ます / た / て)",
    "終止形": "plain form",
    "連体形": "plain form (attributive)",
    "仮定形": "conditional stem (before ば)",
    "命令形": "imperative (command)",
    "意志推量形": "volitional (let's / probably)",
    "已然形": "realis stem",
}
_EUPHONIC = {"促音便", "撥音便", "イ音便", "ウ音便"}  # 書い, 読ん, 帰っ: stems that take て / た


def conj_label(t: Token) -> str:
    """English description of the conjugated form, e.g. '連用形-一般' -> 'continuative stem'."""
    if not t.conj_form:
        return ""
    base, _, variant = t.conj_form.partition("-")
    if t.pos == "形容詞" and base == "連用形":
        return "te/ta stem (〜かっ)" if variant in _EUPHONIC else "adverbial form (〜く)"
    if base == "連用形" and variant in _EUPHONIC:
        return "te/ta stem (sound-changed continuative)"
    if base == "仮定形" and variant == "融合":
        return "conditional (contracted, 〜きゃ / 〜けりゃ)"
    return _FORM_LABELS.get(base, t.conj_form)


def verb_class(t: Token) -> str:
    """'godan' / 'ichidan' / irregular, for verbs."""
    if t.pos != "動詞" or not t.conj_type:
        return ""
    if t.conj_type.startswith("五段"):
        return "godan verb"
    if t.conj_type.startswith(("上一段", "下一段")):
        return "ichidan verb"
    if t.conj_type.startswith("サ行変格"):
        return "irregular verb (する)"
    if t.conj_type.startswith("カ行変格"):
        return "irregular verb (来る)"
    return ""


# --------------------------------------------------------------------------- particles

_PARTICLE_KIND = {
    "格助詞": "case particle",
    "係助詞": "topic / focus particle",
    "副助詞": "adverbial particle",
    "終助詞": "sentence-ending particle",
    "接続助詞": "conjunctive particle",
    "準体助詞": "nominalizing particle",
    "格助詞,引用": "quotation particle",
}

PARTICLE_NOTES = {
    "は": "marks the topic of the sentence",
    "が": "marks the subject (or 'but' between clauses)",
    "を": "marks the direct object",
    "に": "marks a target, destination, time or location of existence",
    "へ": "marks a direction ('toward')",
    "で": "marks where an action happens, or the means / tool",
    "と": "'and' / 'with' / quotes what was said or thought / 'if'",
    "から": "'from' (starting point) or 'because'",
    "まで": "'until' / 'up to'",
    "より": "'than' (comparison) or 'from'",
    "の": "possessive ('s), or turns a phrase into a noun",
    "も": "'also' / 'even' / 'both'",
    "や": "'and' (a non-exhaustive list)",
    "か": "marks a question, or 'or'",
    "ね": "seeking agreement ('right?', 'isn't it?')",
    "よ": "assertion / emphasis ('you know', 'I tell you')",
    "ぞ": "forceful assertion, mostly male speech",
    "ぜ": "casual emphatic, mostly male speech ('you know!')",
    "わ": "soft assertion (traditionally feminine) or mild surprise",
    "さ": "casual emphasis ('you see')",
    "な": "after a verb: 'don't!'; otherwise casual 'right?' / 'hey'",
    "かな": "wondering ('I wonder…')",
    "かい": "casual question (older male speech)",
    "ばかり": "'only' / 'just' / 'nothing but'",
    "だけ": "'only' / 'just'",
    "しか": "'nothing but' (always with a negative: 〜しか〜ない)",
    "ほど": "'about' / 'to the extent of'",
    "など": "'such as' / 'and so on'",
    "なんて": "'such a thing as…' (disbelief or contempt)",
    "さえ": "'even'",
    "すら": "'even' (stronger)",
    "こそ": "emphasizes the word before it ('precisely')",
    "でも": "'even' / 'or something'",
    "って": "casual quotation / topic ('they say…', 'as for…')",
    "とか": "'things like…' / 'or something'",
    "ので": "'because' (objective reason)",
    "のに": "'even though' / 'in order to'",
    "けど": "'but' (casual)",
    "けれど": "'but'",
    "けれども": "'but' (formal)",
    "し": "'and moreover' (listing reasons)",
    "ん": "contraction of の: nominalizes or adds an explanatory tone",
    "ながら": "'while doing'",
    "て": "te-form: connects clauses, makes requests, forms continuous tenses",
    "ば": "'if' (conditional)",
    "たり": "'doing things like… (and…)'",
}


def particle_note(t: Token) -> str:
    """Short English note for a particle, or '' if there isn't one."""
    if t.pos != "助詞":
        return ""
    return PARTICLE_NOTES.get(t.surface, "")


def particle_kind(t: Token) -> str:
    return _PARTICLE_KIND.get(t.pos_detail, "") if t.pos == "助詞" else ""


# --------------------------------------------------------------------------- predicate chains

_NEG_BASES = {"ない", "ぬ", "ねえ", "ねぇ", "なんだ"}
_CHAIN_PARTICLES = {"て", "で", "ば", "ながら", "たり", "だり", "つつ"}
_ALIASES = {
    "せる": "させる",
    "れる": "られる",
    "行く": "いく",
    "来る": "くる",
    "見る": "みる",
    "居る": "いる",
    "有る": "ある",
    "貰う": "もらう",
    "下さる": "くださる",
    "よう": "う",
}


def _is_negative(t: Token) -> bool:
    return t.conj_type == "助動詞-ナイ" or t.dictionary_form in _NEG_BASES


def _key(t: Token) -> str:
    if t.pos == "助詞":
        return t.surface
    if t.surface in ("じゃ", "じゃあ"):
        return "じゃ"
    if _is_negative(t):
        return "NEG"
    base = _ALIASES.get(t.dictionary_form, t.dictionary_form)
    core = base.rstrip("あぁー")  # stretched speech: だあ -> だ, ですう -> です
    if core and core != base and (core in _SINGLE or core in _TE_AUX):
        return core
    return base


def _absorbs(t: Token, prev: Token, nxt: Token | None) -> bool:
    """Can `t` continue a predicate chain whose last token is `prev`?"""
    if t.pos == "助動詞":
        return True
    if t.pos == "助詞":
        if t.pos_detail == "接続助詞":
            return t.surface in _CHAIN_PARTICLES
        # 動くんじゃねえ / 出せねえんだ: the explanatory ん/の joins the auxiliary that follows it
        return t.pos_detail == "準体助詞" and nxt is not None and nxt.pos == "助動詞"
    if t.pos in ("動詞", "形容詞") and t.pos_detail == "非自立可能":
        return _is_negative(t) or (prev.pos == "助詞" and prev.surface in ("て", "で"))
    return False


# (label, note). Labels are short so they read well joined by arrows.
_SINGLE: dict[str, tuple[str, str]] = {
    "させる": ("causative", "make or let someone do something (〜させる)"),
    "られる": ("passive / potential", "is done to; or can do (〜られる). Context decides which"),
    "NEG": ("negative", "'not' (〜ない). ねえ and ん are rougher, casual forms of ない"),
    "たい": ("want to", "wants to do (〜たい)"),
    "たがる": ("wants to (third person)", "shows that someone else wants to (〜たがる)"),
    "た": ("past", "past or completed (〜た)"),
    "ます": ("polite", "polite verb ending (〜ます)"),
    "です": ("polite copula", "'is / am / are' in polite speech (です)"),
    "だ": ("copula", "'is / am / are' (〜だ)"),
    "じゃ": ("copula (contracted)", "casual contraction of では, as in 〜じゃない = 'is not'"),
    "う": ("volitional", "'let's…' / 'I will…' / 'probably' (〜う・〜よう)"),
    "やがる": ("derogatory", "rude or hostile tone, like 'damn' (〜やがる)"),
    "ちゃう": ("completed / regret", "contraction of 〜てしまう: do completely, or unfortunately"),
    "じゃう": ("completed / regret", "contraction of 〜でしまう: do completely, or unfortunately"),
    "ちまう": ("completed / regret", "rough contraction of 〜てしまう"),
    "じまう": ("completed / regret", "rough contraction of 〜でしまう"),
    "てる": ("ongoing state", "contraction of 〜ている: in progress or resulting state"),
    "でる": ("ongoing state", "contraction of 〜でいる: in progress or resulting state"),
    "とく": ("do in advance", "contraction of 〜ておく: do ahead of time / leave as is"),
    "どく": ("do in advance", "contraction of 〜でおく: do ahead of time / leave as is"),
    "て": ("te-form", "connects clauses, makes requests, forms continuous tenses (〜て)"),
    "で": ("te-form", "connects clauses, makes requests, forms continuous tenses (〜で)"),
    "ば": ("conditional", "'if' (〜ば)"),
    "ながら": ("while", "'while doing' (〜ながら)"),
    "たり": ("listing actions", "'doing things like… and…' (〜たり〜たり)"),
    "だり": ("listing actions", "'doing things like… and…' (〜だり〜だり)"),
    "つつ": ("while", "'while / even as' (〜つつ)"),
    "ず": ("without", "'without doing' / literary negative (〜ず)"),
    "まい": ("won't", "'surely won't' / negative volitional (〜まい)"),
    "らしい": ("seems", "'apparently' / 'seems like' (〜らしい)"),
    "ん": ("explanatory", "contraction of の: adds an explanatory or emphatic tone"),
    "の": ("explanatory", "nominalizer or explanatory tone (〜の)"),
}

_TE_AUX = {
    "いる": ("ongoing / resulting state", "in progress, or a state that resulted from an action (〜ている)"),
    "いく": ("going on", "continues, or gradually changes (〜ていく)"),
    "くる": ("coming to", "has come to be, or is coming (〜てくる)"),
    "しまう": ("completed / regret", "do completely, or unfortunately (〜てしまう)"),
    "おく": ("do in advance", "do ahead of time / leave as is (〜ておく)"),
    "みる": ("try doing", "try and see (〜てみる)"),
    "あげる": ("do for someone", "do something for someone else (〜てあげる)"),
    "やる": ("do for someone", "do something for someone, casual / lower status (〜てやる)"),
    "くれる": ("done for me", "someone does something for me or us (〜てくれる)"),
    "くださる": ("please", "polite request, 'please do…' (〜てください)"),
    "もらう": ("have it done", "I get someone to do something for me (〜てもらう)"),
    "いただく": ("have it done (humble)", "I humbly receive someone's action (〜ていただく)"),
    "ある": ("resulting state", "a state left by a deliberate action (〜てある)"),
    "おる": ("ongoing (humble / dialect)", "in progress, humble or dialect for 〜ている (〜ておる)"),
}

# Multi-token patterns; keys use "|" for alternatives. Longest patterns are tried first.
_PATTERNS: list[tuple[tuple[str, ...], tuple[str, str]]] = sorted(
    [
        (("ます", "NEG", "です", "た"), ("polite negative past", "did not (polite) (〜ませんでした)")),
        (
            ("ん|の", "じゃ", "NEG"),
            ("emphatic prohibition", "'don't…!' or 'it's not that…' (〜んじゃない), very common in rough speech"),
        ),
        (("ます", "NEG"), ("polite negative", "does not (polite) (〜ません)")),
        (("ます", "た"), ("polite past", "did (polite) (〜ました)")),
        (("です", "た"), ("polite past", "was / were (polite) (〜でした)")),
        (("だ", "た"), ("past", "was / were (〜だった)")),
        (("NEG", "た"), ("negative past", "did not (〜なかった)")),
        (("ん|の", "だ"), ("explanatory", "explains a reason or adds emphasis (〜んだ / 〜のだ)")),
        (("ん|の", "です"), ("explanatory (polite)", "polite form of 〜んだ (〜のです / 〜んです)")),
        (("NEG", "で"), ("without / please don't", "'without doing' or 'please don't' (〜ないで)")),
    ]
    + [(("て|で", aux), meaning) for aux, meaning in _TE_AUX.items()],
    key=lambda p: -len(p[0]),
)


def _match(keys: list[str], j: int, pattern: tuple[str, ...]) -> bool:
    return j + len(pattern) <= len(keys) and all(
        keys[j + k] in alternatives.split("|") for k, alternatives in enumerate(pattern)
    )


def _single(t: Token, key: str, prev_keys: list[str]) -> tuple[str, str]:
    """Label + note for one auxiliary / particle token."""
    if key == "られる" and "させる" in prev_keys:
        return "passive", "made to do something (〜させられる)"
    if key == "た" and t.conj_form.startswith("仮定形"):
        return "conditional", "'if / when' (〜たら)"
    if key == "NEG" and t.conj_form.startswith("仮定形"):
        return "must (contracted)", "〜なきゃ: contraction of 〜なければ, usually followed by 'must / have to'"
    if key in ("です", "だ") and t.conj_form.startswith("意志推量形"):
        return "probably", "'probably / right?' (〜でしょう / 〜だろう)"
    if key == "だ" and t.pos == "助動詞":
        if t.surface == "に":
            return "adverbial", "turns a na-adjective into an adverb (〜に)"
        if t.surface == "な" and t.conj_form.startswith("連体形"):
            return "attributive", "links a na-adjective to the noun it describes (〜な)"
        if t.surface == "で":
            return "copula (te-form)", "'is … and' / 'being …' (〜で)"
    label, note = _SINGLE.get(key, (f"{t.pos_label}: {t.dictionary_form}", ""))
    if t.conj_form.startswith("命令形") and t.pos == "助動詞":
        note = (note + "; " if note else "") + "imperative (command) form"
    return label, note


def _head_step(t: Token) -> dict:
    if t.pos in ("動詞", "形容詞"):
        form = conj_label(t)
        label = f"{t.dictionary_form} — {form}" if form else t.dictionary_form
    else:
        label = f"{t.dictionary_form} ({t.pos_label})"
    return {"text": t.surface, "label": label, "note": "", "key": "HEAD"}


def _label_chain(chain: list[Token]) -> list[dict]:
    keys = [_key(t) for t in chain]
    steps = [_head_step(chain[0])]
    j = 1
    while j < len(chain):
        for pattern, (label, note) in _PATTERNS:
            if _match(keys, j, pattern):
                span = chain[j : j + len(pattern)]
                steps.append({"text": "".join(t.surface for t in span), "label": label, "note": note, "key": "+".join(pattern)})
                j += len(pattern)
                break
        else:
            label, note = _single(chain[j], keys[j], [s["key"] for s in steps])
            steps.append({"text": chain[j].surface, "label": label, "note": note, "key": keys[j]})
            j += 1
    return steps


_COPULA_KEYS = {"だ", "です", "じゃ", "NEG"}


def _is_chain_head(t: Token, nxt: Token | None) -> bool:
    if t.pos in ("動詞", "形容詞"):
        return True
    # A noun / na-adjective stem only starts a chain when a copula follows it directly
    # (学生じゃない, 静かだった). Nothing else attaches to a noun, so e.g. a mis-tokenized
    # 'なあん + た' is not read as "noun + past".
    return t.pos in ("名詞", "代名詞", "形状詞") and nxt is not None and nxt.pos in ("助動詞", "形容詞") and _key(nxt) in _COPULA_KEYS


def find_units(tokens: list[Token]) -> list[dict]:
    """Predicate chains with at least one attached element, in reading order.

    Each unit: {start, end (exclusive token indexes), text, base, summary, steps[]} where
    steps[0] is the head word and the rest are the attached elements, each with an English
    label and note. `summary` strings the labels together, e.g. 'causative → passive → past'.
    """
    units = []
    i = 0
    while i < len(tokens):
        nxt = tokens[i + 1] if i + 1 < len(tokens) else None
        if not _is_chain_head(tokens[i], nxt):
            i += 1
            continue
        end = i + 1
        while end < len(tokens) and _absorbs(
            tokens[end], tokens[end - 1], tokens[end + 1] if end + 1 < len(tokens) else None
        ):
            end += 1
        if end - i >= 2:
            chain = tokens[i:end]
            steps = _label_chain(chain)
            units.append(
                {
                    "start": i,
                    "end": end,
                    "text": "".join(t.surface for t in chain),
                    "base": chain[0].dictionary_form,
                    "summary": " → ".join(s["label"] for s in steps[1:]),
                    "steps": [{k: v for k, v in s.items() if k != "key"} for s in steps],
                }
            )
        i = max(end, i + 1)
    return units
