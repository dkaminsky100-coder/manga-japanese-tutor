# Manga Reader

A web manga reader for learning Japanese. Upload a chapter (images, `.cbz` or PDF); hovering a
speech bubble shows its text with furigana, a word-by-word dictionary breakdown and common
phrases. Everything runs locally.

```
React + Vite  --HTTP-->  FastAPI
                          |- comic-text-detector (ONNX)  finds speech bubbles
                          |- manga-ocr                   reads vertical/horizontal text
                          |- waifu2x-ncnn-vulkan         optional 2x upscaling (any Vulkan GPU)
                          |- SudachiPy (full dict)       tokens, readings, conjugation
                          |- JMdict (SQLite)             definitions, ranked by part of speech
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
[waifu2x-ncnn-vulkan](https://github.com/nihui/waifu2x-ncnn-vulkan/releases) executable to upscale
low-resolution scans before OCR (a modest accuracy gain on 600-700 px pages).

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

## Tests

```
cd backend  && .venv\Scripts\python -m pytest
cd frontend && npx vitest run
```

JMdict is (c) the Electronic Dictionary Research and Development Group, used under CC BY-SA 4.0.
