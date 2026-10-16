"""One lock for importing and loading the big ML libraries/models.

`transformers` (used by both manga-ocr and the translator) loads its submodules lazily and is not
safe to import for the first time from two threads at once: the loser fails with errors like
"cannot import name 'ViTImageProcessor'". The startup warm-up thread and a request thread can
race for exactly that, so every first-time import / model load takes this lock. It is reentrant
so loaders can call each other.
"""
import threading

LOAD_LOCK = threading.RLock()
