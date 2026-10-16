# Manga Japanese Tutor

A web manga reader for learning Japanese. Upload a chapter (images, `.cbz` or PDF); hovering a
speech bubble shows its text with furigana, a word-by-word dictionary breakdown and common
phrases. Everything runs locally.

```
React + Vite  --HTTP-->  FastAPI
                          |- comic-text-detector (ONNX)  finds speech bubbles
                          |- manga-ocr                   reads vertical/horizontal text
                          |- waifu2x-ncnn-vulkan         optional 2x upscaled copy, used as a second detection pass
                          |- SudachiPy (full dict)       tokens, readings, conjugation
                          |- JMdict (SQLite)             definitions, ranked by part of speech
                          |- grammar rules               verb/adjective chains (causative -> passive -> past), particle notes
                          |- opus-mt-ja-en               rough sentence translation (on demand)
```

## Setup

Python 3.12 and Node 20+.

```
# backend
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

If pip fails with `CERTIFICATE_VERIFY_FAILED` (antivirus/proxy HTTPS interception), use
`pip install --use-feature=truststore ...` so it trusts the Windows certificate store.
PyTorch is the CPU build from `https://download.pytorch.org/whl/cpu`.

One-time data downloads (kept out of git, under `data/`):

1. **Text detector** - `comictextdetector.pt.onnx` from the
   [manga-image-translator `beta-0.3` release](https://github.com/zyddnys/manga-image-translator/releases/tag/beta-0.3)
   into `data/models/`.
2. **Dictionary** - `jmdict-eng-*.json.zip` from
   [jmdict-simplified](https://github.com/scriptin/jmdict-simplified/releases) (the full file, not
   "common"), unzip it, then build the SQLite file:
   `.venv\Scripts\python -m app.dict.import_jmdict path\to\jmdict-eng-3.x.json`
3. The manga-ocr model (~400 MB) and the translation model (`Helsinki-NLP/opus-mt-ja-en`, ~300 MB)
   download from Hugging Face the first time the server starts.

Optional: copy `backend/.env.example` to `backend/.env` and set `WAIFU2X_EXE` to a
[waifu2x-ncnn-vulkan](https://github.com/nihui/waifu2x-ncnn-vulkan/releases) executable. Each page is then
also detected on a 2x upscaled copy, which finds blocks the original misses; the OCR itself always
reads the original pixels (on the test pages, reading upscaled crops was less accurate).

```
# frontend
cd frontend
npm install
```

## Run

```
cd backend  && .venv\Scripts\python -m uvicorn app.main:app --port 8000
cd frontend && npm run dev          # open http://localhost:5173
```

## Correcting OCR mistakes

Hover a bubble and click **Edit text**, fix the text, then **Save** (or Ctrl+Enter; plain Enter is left
for confirming Japanese input). The furigana, dictionary, grammar and translation update immediately.
Corrected bubbles show an *edited* badge, what the OCR originally read, and a **Reset to OCR** button.
Corrections are kept when a page is read again after a pipeline change (matched to the new boxes by
position; if the bubble is no longer detected the corrected block is kept as it was).

## Tests

```
cd backend  && .venv\Scripts\python -m pytest
cd frontend && npx vitest run
```

## License

All rights reserved. You may download and use the software unmodified, but not modify or redistribute
it; see [LICENSE.md](LICENSE.md). The models and dictionaries it downloads are not part of this
repository and keep their own licenses (listed in LICENSE.md). JMdict is (c) the Electronic Dictionary
Research and Development Group, used under CC BY-SA 4.0.
