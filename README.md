# audiodoc

Backend for a Telegram bot: Whisper audio transcription and text extraction from documents.

A standalone FastAPI service for a Telegram bot. It exposes `/transcribe` for Whisper audio recognition and `/process-document` for Document Engine text extraction. The bot remains an HTTP client; image, animation, and video processing stay on the bot side.

## Features

- Speech recognition with `faster-whisper`.
- Text extraction from PDF (including OCR for scans), DOCX, XLSX, PPTX, ODT, ODS, ODP, EPUB, FB2, DJVU (including OCR), TXT, Markdown, HTML, XML, CSV, and RTF.
- Separate Bearer keys for Whisper and Document Engine.
- Limits for uploads, audio duration, processing time, extracted text, tables, OCR, subprocesses, and work queues.
- Dependency diagnostics at `/ready`, request correlation with `X-Request-ID`, and log-secret redaction.

Legacy Office formats (`.doc`, `.xls`, `.ppt`) and standalone images are unsupported. Image, animation, and video handling belongs to the bot.

## Requirements

Python 3.11 or newer is required.

Example Debian/Ubuntu system packages:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip tesseract-ocr tesseract-ocr-rus tesseract-ocr-eng djvulibre-bin
```

OCR requires Tesseract and the `rus`/`eng` language data. DJVU requires `djvutxt`, `djvused`, and `ddjvu`. Check them with authenticated `GET /ready`.

## Release installer

After the first GitHub Release is published, the installer can set up audiodoc, create two separate random API keys, optionally download the Whisper model, and prepare a bot configuration snippet. The installer does not enable or start its optional user systemd unit.

Download the script first, inspect it, and then run it (do not pipe an unreviewed script directly into a shell):

```bash
curl -fsSLo install.sh https://raw.githubusercontent.com/WhlteAdmln/audiodoc/main/install.sh
less install.sh
sh install.sh --latest --systemd
```

Use `--nightly` for the newest published prerelease. The installer supports `--host`, `--port`, `--model`, `--device`, `--compute-type`, and `--no-model`; run `sh install.sh --help` for details. It binds to `127.0.0.1` by default. For a two-machine deployment, use the backend's private/VPN address and restrict its port to the bot host. For a production system service with a dedicated account and filesystem sandbox, follow [the deployment guide](deploy/README.md).

The first stable or prerelease must exist before the corresponding release channel can be installed. `--latest` requires a stable GitHub Release; `--nightly` requires a published prerelease.

## Quick start

From the project root:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-lock.txt
cp .env.example .env
chmod 600 .env
```

Edit `.env` and set two different, long random secrets: `AUDIODOC_AUDIO_KEY` and `AUDIODOC_DOCUMENT_KEY`. Configure the matching values in the bot's environment. Do not enable `ALLOW_UNAUTHENTICATED` on a production server.

Generate a key with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Run locally:

```bash
uvicorn app:app --host 127.0.0.1 --port 8000
```

For a two-machine deployment, bind the service to a private/VPN address, not `0.0.0.0`. UFW, WireGuard, nginx, and systemd examples are in `deploy/`. Replace all example addresses and paths before use; allow administrator SSH access before enabling firewall rules.

On first use, `faster-whisper` may download a model. For an isolated server, prepare a local model first, set `WHISPER_MODEL_PATH`, and enable `WHISPER_OFFLINE=true`; see `docs/operations.md`.

## Verify the service

```bash
curl -i http://127.0.0.1:8000/health
curl -i http://127.0.0.1:8000/ready \
  -H "Authorization: Bearer $AUDIODOC_DOCUMENT_KEY"
```

`/health` is an unauthenticated liveness endpoint. `/ready` reports native document-processing dependencies and requires the document key. `/docs` and `/openapi.json` are disabled by default.

Test a document upload:

```bash
curl -i \
  -H "Authorization: Bearer $DOCUMENT_API_KEY" \
  -F "file=@sample.txt" \
  http://127.0.0.1:8000/process-document
```

For the bot, set `AUDIODOC_URL` to the base URL without an endpoint path; the bot appends `/transcribe` and `/process-document`. Avoid putting production secrets directly into shell command arguments.

## Environment settings

The `.env.example` file lists all environment-backed settings and their defaults.

The legacy names `WHISPER_API_KEY` and `DOCUMENT_API_KEY` remain accepted as fallbacks when the corresponding new setting is empty. The new setting takes precedence. Legacy-name use produces a deprecation warning at startup; migrate within two minor releases.

| Variable | Default | Purpose |
| --- | ---: | --- |
| `AUDIODOC_AUDIO_KEY` | empty | Dedicated Bearer key for `/transcribe`; empty only with local auth bypass |
| `AUDIODOC_DOCUMENT_KEY` | empty | Dedicated Bearer key for `/process-document` and `/ready` |
| `ALLOW_UNAUTHENTICATED` | `false` | Local development bypass; never enable on a production server |
| `BACKEND_TEMP_DIR` | `tmp/` in the project root | Private temporary-file directory |
| `MAX_AUDIO_SIZE` | `26214400` | Maximum audio upload size in bytes (25 MiB) |
| `MAX_AUDIO_DURATION` | `600` | Maximum audio duration in seconds |
| `MAX_CONCURRENT_TRANSCRIPTIONS` | `1` | Active transcription workers |
| `MAX_WAITING_DOCUMENTS` | `4` | Waiting document jobs (2 active workers) |
| `MAX_WAITING_TRANSCRIPTIONS` | `4` | Waiting transcription jobs |
| `WHISPER_MODEL_SIZE` | `small` | Model identifier when no local path is set |
| `WHISPER_MODEL_PATH` | empty | Optional pre-downloaded local model path; takes precedence over model size |
| `WHISPER_DEVICE` | `cpu` | Model device (`cpu` or supported `cuda`) |
| `WHISPER_COMPUTE_TYPE` | `int8` | Compute type compatible with the selected device |
| `WHISPER_OFFLINE` | `false` | Passes `local_files_only=true` to prevent model downloads |
| `WHISPER_CPU_THREADS` | `6` | Whisper CPU thread count |
| `WHISPER_LANGUAGE` | `ru` | Language hint for transcription |
| `WHISPER_BEAM_SIZE` | `5` | Whisper beam size |
| `ENABLE_DOCS` | `false` | Enables `/docs` and `/openapi.json`; development only |
| `LOG_LEVEL` | `INFO` | Python logging level |

Other Document Engine limits are constants in `backend/document_engine/limits.py`: 50 MiB per document, 500 pages, two million extracted characters, a 180-second processing deadline, two concurrent documents, and separate ZIP/table/image/OCR/DJVU limits.

## Tests

Install development dependencies and run the test suites separately:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m pytest -q -m integration
```

Integration tests need Tesseract with the `rus` and `eng` language data, plus DjVuLibre. They use a fake Whisper model; no real Whisper model is downloaded or loaded. Install the Python dependencies from `requirements-lock.txt` before running them. See `docs/operations.md`.

## Documentation

- [Architecture (EN)](docs/architecture.md) · [Архитектура (RU)](docs/architecture.ru.md)
- [HTTP API](docs/api.md)
- [Telegram bot connection guide](docs/connecting-the-bot.md)
- [Operations](docs/operations.md)
- [Adding a format](docs/adding-a-format.md)
- [Security checklist](docs/security-checklist.md)
- [Deployment acceptance checklist (historical)](docs/history/final-acceptance.md)
- [Deployment examples](deploy/README.md)
- [Refactoring history](docs/history/REFACTORING_LOG.md)
