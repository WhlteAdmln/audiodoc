# Operations guide

This document describes a conservative, single-service deployment. Adapt paths, addresses, resource caps, and network policy to the actual host. Test changes before applying them to the working service.

## 1. Operating-system dependencies

On Debian/Ubuntu, the package names commonly used for the required programs are:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip \
  tesseract-ocr tesseract-ocr-rus tesseract-ocr-eng djvulibre-bin
```

Verify the command-line tools:

```bash
command -v tesseract
command -v djvutxt
command -v djvused
command -v ddjvu
tesseract --list-langs
```

The Python packages are installed from the pinned lock file:

```bash
python3 -m venv venv
. venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-lock.txt
```

For tests, install `requirements-dev.txt` as well. OCR integration tests need Tesseract and its language data. DJVU integration tests need DjVuLibre. Whisper integration tests need a usable local model and its runtime dependencies.

## 2. Environment file and permissions

Start from `.env.example`; do not store real values in archives or source control. Set two different, long, random secrets:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Copy the generated values into `WHISPER_API_KEY` and `DOCUMENT_API_KEY` in the backend `.env`, and set the corresponding same values in the bot's environment. Keep `ALLOW_UNAUTHENTICATED=false`.

For a manually managed service user:

```bash
chmod 600 .env
```

For the sample systemd setup where `.env` is readable by the service group and not writable by the service user, use the ownership/mode described in `deploy/README.md` (`root:mediabackend`, mode `640`). The application sets `umask(077)` and creates its configured temp directory with restrictive permissions. The temp directory should be writable only by the service account (`chmod 700`).

Never put a secret directly in an `ExecStart` command-line argument. Use `EnvironmentFile=`. Do not include `.env`, user documents, audio, database files, or production logs in an archive. Do not run downloaded shell installers such as `curl ... | sh` without first downloading, inspecting, and verifying the script.

## 3. Whisper model and offline startup

If the service is allowed temporary internet access during provisioning, download the model on a trusted machine with the same compatible `faster-whisper` environment. For the `small` model, one supported workflow is:

```bash
python -c "from faster_whisper.utils import download_model; print(download_model('small', output_dir='/opt/media-backend/models/small'))"
```

Copy the complete model directory to the backend host, set:

```ini
WHISPER_MODEL_PATH=/opt/media-backend/models/small
WHISPER_OFFLINE=true
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
```

`WHISPER_MODEL_PATH` takes precedence over `WHISPER_MODEL_SIZE`. Offline mode passes `local_files_only=true` to the model loader; it does not install system libraries or repair an incomplete model directory. Check file ownership/read permissions for the service user before disabling network egress. GPU deployments must select a compatible `WHISPER_DEVICE` and `WHISPER_COMPUTE_TYPE`; GPU access may require additional systemd device permissions and competes with the LLM for VRAM.

## 4. Start and stop

Local test run:

```bash
. venv/bin/activate
uvicorn app:app --host 127.0.0.1 --port 8000
```

For a remote bot, bind to a private/VPN address (example `10.8.0.1`) or keep Uvicorn on loopback behind a TLS reverse proxy. Do not bind to `0.0.0.0` on an untrusted network. For systemd, start with the example in `deploy/media-backend.service.example`, edit it, then run:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now media-backend
systemctl status media-backend
```

Stop/restart:

```bash
sudo systemctl stop media-backend
sudo systemctl restart media-backend
```

## 5. Health and readiness

`GET /health` is an unauthenticated liveness probe and returns the configured model name and `loaded` flag:

```bash
curl -i http://127.0.0.1:8000/health
```

`GET /ready` is protected by `DOCUMENT_API_KEY`. It reports `tesseract`, the discovered `languages`, `djvulibre` (true only when all three programs are found), and `model_loaded`:

```bash
curl -i http://127.0.0.1:8000/ready \
  -H "Authorization: Bearer <DOCUMENT_API_KEY>"
```

Interpretation:

| Field | If false or incomplete | What to check |
|---|---|---|
| `tesseract` | Executable not found | Install `tesseract-ocr`; verify the service PATH |
| `languages` | One or more OCR languages absent | Install `tesseract-ocr-rus` and/or `tesseract-ocr-eng`; run `tesseract --list-langs` as the service user |
| `djvulibre` | One or more programs absent | Install `djvulibre-bin`; check `djvutxt`, `djvused`, `ddjvu` on PATH |
| `model_loaded` | Whisper has not loaded | Review service logs, model path, permissions, device/compute compatibility, and model files |

The readiness endpoint is diagnostic. A false field does not trigger automatic installation.

## 6. Logs and request tracing

When running under systemd, view live logs and recent history with:

```bash
sudo journalctl -u media-backend -f
sudo journalctl -u media-backend -n 200 --no-pager
```

Each HTTP request receives an `X-Request-ID` (provided by the client if it matches the allowed pattern, otherwise generated by the backend). The ID is returned in the response header and appears in the log format. Use it to correlate the bot's log and backend's log. Do not log file contents, extracted text, transcripts, authorization headers, or raw filenames. The backend adds redaction filters for configured keys and token-like values.

For persistent journal storage, review `/etc/systemd/journald.conf` and consider `Storage=persistent` and `SystemMaxUse=500M`. Restrict access to journal records. Keep both machines' clocks synchronized (`timedatectl status`).

## 7. Troubleshooting

| Symptom / HTTP status | Likely cause | Action |
|---|---|---|
| Startup fails with missing-key message | One or both API keys are empty | Set distinct `WHISPER_API_KEY` and `DOCUMENT_API_KEY`; keep bypass disabled |
| `401 Unauthorized` | Key missing, incorrect, or sent to the wrong endpoint | Verify the matching bot/backend key pair and Bearer header; do not paste the key into logs |
| `400` for a document | Corrupt, unsupported, or prohibited input | Try a valid supported file; do not disable archive/XML guards |
| `413` | File or request exceeds a configured limit | Check the file size and `MAX_AUDIO_SIZE` / document size limit |
| `503` with `Retry-After` | Work queue is full | Reduce request pressure or tune waiting limits with available memory/CPU in mind |
| `503` from `/ready` or OCR/DJVU | A required native dependency is unavailable | Install OS package; inspect `/ready` and service PATH |
| `504` on a document | Overall document deadline elapsed | Use a smaller file or reduce OCR/table work; do not blindly raise the deadline |
| `500 Internal server error` | Unexpected internal error | Find the matching `X-Request-ID` in server logs; keep traceback server-side |
| Whisper fails at startup | Model path, files, device, compute type, or runtime dependency mismatch | Check local model contents and permissions; temporarily test a known compatible config |
| `/docs` returns `404` | Expected when `ENABLE_DOCS=false` | Enable only in a trusted development environment, then restart |

## 8. Dependency maintenance

- Install OS security updates regularly, especially Tesseract, DjVuLibre, and image libraries.
- For Python dependency updates, create a new virtual environment from the reviewed lock file, run unit and integration tests, switch the service only after tests pass, and retain the old environment for rollback.
- Run `pip-audit -r requirements-lock.txt` periodically on a machine with package-index access. Review the findings; do not blindly upgrade parser libraries directly on production.
- After changing the deployed code, regenerate the integrity baseline described in `deploy/README.md` and verify it periodically.

## 9. Safe rollback

Keep the previous delivery archive and the previous virtual environment. Stop the service, restore the previous verified code and matching environment, check ownership/permissions and `.env` path, then start the service and verify `/health`, `/ready`, one document request, and one transcription. Never restore secrets from an archive; restore them from the host's protected environment file.
