# audiodoc HTTP API

Base URL is `http://HOST:PORT` inside a trusted private network or VPN, or an HTTPS URL in front of a TLS proxy. Processing endpoints require their dedicated `Authorization: Bearer <key>` header. Do not reuse the same secret for both endpoints.

The Telegram bot sends `POST` requests as `multipart/form-data`. The uploaded file field is named `file`. Existing bot clients do not need to send any of the optional headers or fields described below.

## Machine-readable error codes

Typed application errors return the existing `detail` together with a stable `code`:

```json
{"detail":"...", "code":"..."}
```

Clients should use `code` for programmatic handling and may continue to display `detail` to users.

| Code | Status | Endpoint | Meaning |
| --- | ---: | --- | --- |
| `internal_error` | 500 | Both processing endpoints | Unexpected internal failure |
| `server_busy` | 503 | Both processing endpoints | The bounded work queue is full; `Retry-After: 30` is returned |
| `document_rejected` | 400 | `/process-document` | The document cannot be processed |
| `unsupported_format` | 400 | `/process-document` | The format is not supported |
| `payload_too_large` | 413 | `/process-document` | The processing payload exceeds its configured limit |
| `processing_timeout` | 504 | `/process-document` | Document processing exceeded its deadline |
| `dependency_missing` | 503 | `/process-document` | A required native dependency is unavailable |
| `invalid_audio` | 400 | `/transcribe` | The uploaded file is not decodable audio |
| `audio_too_long` | 400 | `/transcribe` | The uploaded audio exceeds the configured duration |
| `model_not_ready` | 503 | `/transcribe` | The Whisper model is not ready |
| `transcription_timeout` | 504 | `/transcribe` | Transcription exceeded its deadline |

Authentication failures, request validation errors, and request-size rejections raised before typed application processing retain their existing response formats.

## `GET /health`

Unauthenticated liveness endpoint. It reports the configured model identifier and whether the model has loaded. When `WHISPER_MODEL_PATH` is set, `model` is the local model directory name; otherwise it is `WHISPER_MODEL_SIZE`.

Example response:

```json
{"status":"ok","model":"small","loaded":true}
```

This endpoint does not check Tesseract or DjVuLibre. Use `/ready` for that diagnostic.

## `GET /ready`

Requires `AUDIODOC_DOCUMENT_KEY` in `Authorization: Bearer <key>`. Reports whether Tesseract is installed, which language data it can see, whether all required DjVuLibre programs are on `PATH`, and whether the Whisper model is loaded.

Example response (actual booleans/languages depend on the host):

```json
{"tesseract":true,"languages":["eng","osd","rus"],"djvulibre":true,"model_loaded":true}
```

An absent tool or language is reported as a diagnostic value; the endpoint does not install packages. A missing or invalid key returns `401`.

## `POST /transcribe`

Recognizes an audio file. Authentication key: `AUDIODOC_AUDIO_KEY`.

Request:

```bash
curl -X POST \
  -H "Authorization: Bearer <AUDIODOC_AUDIO_KEY>" \
  -F "file=@voice.ogg" \
  http://HOST:8000/transcribe
```

Response `200`:

```json
{"text":"recognized text","language":"ru","duration":12.3}
```

| Status | Meaning |
| ---: | --- |
| 400 | Audio is unreadable (`invalid_audio`) or exceeds `MAX_AUDIO_DURATION` (`audio_too_long`) |
| 401 | Missing or invalid audio key |
| 413 | Upload exceeds `MAX_AUDIO_SIZE` or request-body limit |
| 503 | Whisper model is not loaded (`model_not_ready`) or the bounded work queue is full (`server_busy`; `Retry-After: 30`) |
| 504 | Transcription deadline elapsed (`transcription_timeout`) |
| 500 | Unexpected internal failure (`internal_error`); implementation details are not returned |

## `POST /process-document`

Extracts text from a supported document. Authentication key: `AUDIODOC_DOCUMENT_KEY`.

Request without the optional text budget:

```bash
curl -X POST \
  -H "Authorization: Bearer <AUDIODOC_DOCUMENT_KEY>" \
  -F "file=@document.pdf" \
  http://HOST:8000/process-document
```

Optional multipart field `max_characters` is an integer between 1 and the server maximum. It can only reduce extraction work; it cannot raise the configured server limit. Old clients that omit this field continue to work.

```bash
curl -X POST \
  -H "Authorization: Bearer <AUDIODOC_DOCUMENT_KEY>" \
  -F "file=@document.pdf" \
  -F "max_characters=12288" \
  http://HOST:8000/process-document
```

Response `200`:

```json
{"format":"pdf","text":"extracted text","characters":1234,"truncated":false}
```

`format`, `text`, and `characters` are the required fields the bot validates. `truncated` is an additional boolean field; existing clients may ignore it. `characters` is the length of the returned text.

| Status | Meaning |
| ---: | --- |
| 400 | Empty, corrupt, prohibited XML, or unsupported document (`document_rejected`, `unsupported_format`) |
| 401 | Missing or invalid document key |
| 413 | Document processing payload exceeds its configured limit (`payload_too_large`); early request-size rejections retain their existing response format |
| 503 | A required native dependency is missing (`dependency_missing`), or the bounded work queue is full (`server_busy`; `Retry-After: 30`) |
| 504 | `DOCUMENT_PROCESSING_TIMEOUT` elapsed (`processing_timeout`) |
| 500 | Unexpected internal failure (`internal_error`); implementation details are not returned |

### Supported formats

PDF (OCR for pages without a text layer), DOCX, XLSX, PPTX, ODT, ODS, ODP, EPUB, FB2, DJVU (OCR for scanned pages), TXT, MD, RTF, HTML, XML, CSV.

Unsupported: legacy Office binary formats `.doc`, `.xls`, `.ppt`, and standalone image files. Image, animation, and video processing are outside this service.

## Optional correlation header: `X-Request-ID`

A client may send an identifier containing 8–64 ASCII letters, digits, dots, underscores, or hyphens. The backend validates it, generates a UUID when absent/invalid, echoes it in the response header, and includes it in log records. Do not put personal data or secrets in this value.

## Authentication and compatibility

- `/health` is intentionally unauthenticated.
- `/ready` and `/process-document` use `AUDIODOC_DOCUMENT_KEY`.
- `/transcribe` uses `AUDIODOC_AUDIO_KEY`.
- During migration, `WHISPER_API_KEY` and `DOCUMENT_API_KEY` are fallbacks only when their corresponding new keys are empty. New keys take precedence; using legacy names produces a startup deprecation warning.
- `ALLOW_UNAUTHENTICATED=true` is only for isolated local development and must remain `false` in production.
- The bot's established paths, multipart field `file`, and required successful response fields remain unchanged.
