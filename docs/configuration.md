# Configuration reference

`~/.env` (or `$AUDIODOC_HOME/.env`) contains backend settings. Start with `.env.example`, keep the file readable only by the service administrator/account, and never commit real secrets. For a manually managed single-user install, use `chmod 600 .env`; a dedicated system service may use `root:audiodoc` with mode `640` as described in [Production deployment](operations.md#production-deployment).

Generate independent keys for audio and documents:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Set the generated values in `AUDIODOC_AUDIO_KEY` and `AUDIODOC_DOCUMENT_KEY`. The keys must be different. `AUDIODOC_HOME` is read from the process environment before the `.env` file is loaded; it selects the application home containing `.env`, `.venv`, `tmp/`, and `models/`.

## Environment settings

The defaults below match `.env.example` and the CLI defaults. Empty means that no value is supplied in `.env`.

| Variable | Default | Purpose | Example |
| --- | --- | --- | --- |
| `AUDIODOC_HOME` | `~/audiodoc` | Application home; set in the process environment, not in `.env` | `AUDIODOC_HOME=/opt/audiodoc` |
| `AUDIODOC_HOST` | `127.0.0.1` | Bind address used by the `audiodoc run` command and the default URL printed by `audiodoc pair` | `AUDIODOC_HOST=10.8.0.1` |
| `AUDIODOC_PORT` | `8000` | Listen port used by the CLI and the default URL printed by `audiodoc pair` | `AUDIODOC_PORT=8000` |
| `AUDIODOC_AUDIO_KEY` | empty | Bearer key for `POST /transcribe`; required unless the local authentication bypass is enabled | `AUDIODOC_AUDIO_KEY=<random-audio-key>` |
| `AUDIODOC_DOCUMENT_KEY` | empty | Separate Bearer key for `POST /process-document` and `GET /ready` | `AUDIODOC_DOCUMENT_KEY=<random-document-key>` |
| `ALLOW_UNAUTHENTICATED` | `false` | Local-development authentication bypass; never enable on a production server | `ALLOW_UNAUTHENTICATED=false` |
| `BACKEND_TEMP_DIR` | `$AUDIODOC_HOME/tmp` | Private directory for temporary uploads and intermediate files; relative paths resolve under the user's home directory (`$HOME`) | `BACKEND_TEMP_DIR=/var/tmp/audiodoc` |
| `MAX_AUDIO_SIZE` | `26214400` | Maximum audio upload size in bytes (25 MiB) | `MAX_AUDIO_SIZE=20971520` |
| `MAX_AUDIO_DURATION` | `600` | Maximum audio duration in seconds | `MAX_AUDIO_DURATION=300` |
| `MAX_CONCURRENT_TRANSCRIPTIONS` | `1` | Number of active transcription jobs | `MAX_CONCURRENT_TRANSCRIPTIONS=1` |
| `MAX_WAITING_TRANSCRIPTIONS` | `4` | Maximum transcription jobs waiting in the queue | `MAX_WAITING_TRANSCRIPTIONS=2` |
| `MAX_WAITING_DOCUMENTS` | `4` | Maximum document jobs waiting in the queue | `MAX_WAITING_DOCUMENTS=2` |
| `WHISPER_MODEL_SIZE` | `small` | Model identifier used when `WHISPER_MODEL_PATH` is empty | `WHISPER_MODEL_SIZE=small` |
| `WHISPER_MODEL_PATH` | empty | Path to a pre-downloaded local Whisper model; takes precedence over the model size | `WHISPER_MODEL_PATH=/opt/audiodoc/models/small` |
| `WHISPER_DEVICE` | `cpu` | Inference device | `WHISPER_DEVICE=cpu` |
| `WHISPER_COMPUTE_TYPE` | `int8` | Compute type compatible with the selected device | `WHISPER_COMPUTE_TYPE=int8` |
| `WHISPER_OFFLINE` | `false` | Loads only local model files and prevents model downloads | `WHISPER_OFFLINE=true` |
| `WHISPER_CPU_THREADS` | `6` | CPU threads used by Whisper | `WHISPER_CPU_THREADS=6` |
| `WHISPER_LANGUAGE` | `ru` | Language hint passed to transcription | `WHISPER_LANGUAGE=ru` |
| `WHISPER_BEAM_SIZE` | `5` | Whisper beam size | `WHISPER_BEAM_SIZE=5` |
| `WHISPER_TIMEOUT` | `180` | Timeout in seconds for the Whisper model operation | `WHISPER_TIMEOUT=180` |
| `ENABLE_DOCS` | `false` | Enables `/docs` and `/openapi.json`; keep disabled on production deployments unless access is restricted | `ENABLE_DOCS=false` |
| `LOG_LEVEL` | `INFO` | Python logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`) | `LOG_LEVEL=INFO` |
| `WHISPER_API_KEY` (legacy) | empty | Deprecated fallback for `AUDIODOC_AUDIO_KEY`, used only when the new name is empty | `WHISPER_API_KEY=<old-audio-key>` |
| `DOCUMENT_API_KEY` (legacy) | empty | Deprecated fallback for `AUDIODOC_DOCUMENT_KEY`, used only when the new name is empty | `DOCUMENT_API_KEY=<old-document-key>` |

The new key names take precedence over the legacy fallbacks. Using a legacy name emits a deprecation warning; migrate within two minor releases. Multiple comma-separated values are accepted for each current key during a rotation window. Do not combine the audio and document keys.

The Document Engine also enforces limits that are not environment settings, including document size, page count, extracted characters, processing deadline, and active document workers. See `audiodoc/document_engine/limits.py` for those fixed limits.

## Generate bot settings with `audiodoc pair`

Run this command on the backend host after both backend keys have been set in its `.env`:

```bash
audiodoc pair
```

It prints the bot-side `AUDIODOC_URL`, `AUDIODOC_AUDIO_KEY`, and `AUDIODOC_DOCUMENT_KEY` assignments. The default URL is derived from `AUDIODOC_HOST` and `AUDIODOC_PORT`; wildcard bind addresses are rendered as loopback in the printed URL. To override the URL (for example, with a VPN address or HTTPS hostname), use:

```bash
audiodoc pair --url http://10.8.0.1:8000
```

The command requires both backend keys to be configured. Its output contains live credentials: treat it as a secret, transfer it to the bot host through a protected channel, and do not paste it into tickets, logs, or shared terminal recordings. The URL must be the base URL only, without `/transcribe` or `/process-document`.

For bot-side timeout settings, network layouts, end-to-end verification, and key rotation, see [Connecting the Telegram bot](connecting-the-bot.md). For service startup, file permissions, and production hardening, see [Operations](operations.md).
