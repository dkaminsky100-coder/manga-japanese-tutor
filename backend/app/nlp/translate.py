"""Local Japanese -> English machine translation (Helsinki-NLP opus-mt-ja-en, MarianMT).

This is a small general-purpose model: fine for plain sentences, unreliable on slang and
tough-guy speech, so the UI labels its output as a rough translation.
"""
from __future__ import annotations

import threading

from ..model_lock import LOAD_LOCK

MODEL_NAME = "Helsinki-NLP/opus-mt-ja-en"
MAX_INPUT_CHARS = 400

_generate_lock = threading.Lock()  # one translation at a time on the single model
_model = None
_tokenizer = None


def _load() -> None:
    global _model, _tokenizer
    with LOAD_LOCK:  # see model_lock.py: first-time imports must not race with other loaders
        if _model is not None:
            return
        try:  # use the OS trust store so the first download works behind HTTPS interception
            import truststore

            truststore.inject_into_ssl()
        except ImportError:
            pass
        from transformers import MarianMTModel, MarianTokenizer

        _tokenizer = MarianTokenizer.from_pretrained(MODEL_NAME)
        _model = MarianMTModel.from_pretrained(MODEL_NAME).eval()


def warm_up() -> None:
    _load()


def translate(text: str) -> str:
    """Translate one block of Japanese text. Raises on model failure."""
    text = text.strip()[:MAX_INPUT_CHARS]
    if not text:
        return ""
    _load()
    import torch  # already imported by the model load above

    with _generate_lock, torch.no_grad():
        out = _model.generate(
            **_tokenizer([text], return_tensors="pt"),
            num_beams=4,
            max_length=128,
            no_repeat_ngram_size=3,  # stops loops like "Don't move! Don't move! Don't move!"
        )
    return _tokenizer.decode(out[0], skip_special_tokens=True).strip()
