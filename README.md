# audiodoc

Backend for a Telegram bot: Whisper audio transcription and document text extraction.

A standalone FastAPI service. It exposes `/transcribe` for audio and `/process-document` for document text. The bot remains an HTTP client; image, animation, and video processing stay on the bot side.

## Features

- Speech recognition with `faster-whisper`.
- Text extraction from PDF (including OCR), DOCX, XLSX, PPTX, ODT, ODS, ODP, EPUB, FB2, DJVU (including OCR), TXT, Markdown, HTML, XML, CSV, and RTF.
- Separate Bearer keys for Whisper and Document Engine.
- Bounded upload sizes, processing time, extracted text, and work queues.
- Dependency diagnostics at `/ready`, request correlation with `X-Request-ID`, and log-secret redaction.

Legacy Office formats (`.doc`, `.xls`, `.ppt`) and standalone images are unsupported. Image, animation, and video handling belongs to the bot.

## Requirements

Python 3.11 or newer. On Debian/Ubuntu, install the native OCR and DJVU tools:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip tesseract-ocr tesseract-ocr-rus tesseract-ocr-eng djvulibre-bin
```

## Installation

### 1. Release installer

The installer verifies release checksums and installs into `~/audiodoc/.venv` by default. It requires Linux with glibc, Python 3.11+, `venv`, `curl`, and `sha256sum` (Alpine is unsupported). Download and inspect it before running:

```bash
curl -fsSLo install.sh https://raw.githubusercontent.com/WhlteAdmln/audiodoc/main/install.sh
less install.sh
sh install.sh --no-model --systemd
```

Use `--model`, `--device`, `--compute-type`, `--host`, and `--port` to configure the install; `--no-model` skips the model download. `--systemd` creates a per-user unit but does not enable or start it. Set `AUDIODOC_HOME` to change the install directory. Upgrade guidance is in [Operations](docs/operations.md).

### 2. Install a release wheel

Download the wheel and `constraints.txt` from the same GitHub Release, then install either with pipx or pip:

```bash
pipx install --pip-args="--constraint constraints.txt" ./audiodoc-*.whl
# or
python -m pip install --constraint constraints.txt ./audiodoc-*.whl
audiodoc init
audiodoc doctor
```

### 3. Install from a source checkout

```bash
git clone https://github.com/WhlteAdmln/audiodoc.git
cd audiodoc
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-lock.txt
cp .env.example .env
chmod 600 .env
```

## Configuration

Set different, long random values for `AUDIODOC_AUDIO_KEY` and `AUDIODOC_DOCUMENT_KEY`; keep `ALLOW_UNAUTHENTICATED=false` outside local development. Generate a key with `python -c "import secrets; print(secrets.token_urlsafe(32))"`. See [Configuration](docs/configuration.md) for every setting, defaults, examples, and the `audiodoc pair` command. See the [bot connection guide](docs/connecting-the-bot.md) for bot-side settings.

## Run and verify

For a local source-checkout run:

```bash
uvicorn app:app --host 127.0.0.1 --port 8000
curl -i http://127.0.0.1:8000/health
curl -i http://127.0.0.1:8000/ready \
  -H "Authorization: Bearer $AUDIODOC_DOCUMENT_KEY"
```

`/health` is unauthenticated. `/ready` requires `AUDIODOC_DOCUMENT_KEY`. Bind to a private/VPN address or loopback behind a TLS reverse proxy; do not expose the service on an untrusted network. For offline startup, prepare a local model and set `WHISPER_MODEL_PATH` and `WHISPER_OFFLINE=true`; see [Operations](docs/operations.md).

## Tests

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m pytest -q -m integration
```

Integration tests require Tesseract with `rus` and `eng` data plus DjVuLibre. They use a fake Whisper model and do not load a real model.

## Documentation

- [Architecture](docs/architecture.md) · [Архитектура](docs/architecture.ru.md)
- [HTTP API](docs/api.md) · [Configuration](docs/configuration.md)
- [Telegram bot connection](docs/connecting-the-bot.md)
- [Operations and production deployment](docs/operations.md)
- [Adding a format](docs/adding-a-format.md) · [Security checklist](docs/security-checklist.md)
