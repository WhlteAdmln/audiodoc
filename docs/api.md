# API Media Backend

Base URL is `http://HOST:PORT` inside a trusted private network or VPN, or an HTTPS URL in front of a TLS proxy. Processing endpoints require their dedicated `Authorization: Bearer <key>` header. Do not reuse the same secret for both endpoints.

The Telegram bot sends `POST` requests as `multipart/form-data`. The uploaded file field is named `file`. Existing bot clients do not need to send any of the optional headers or fields described below.

## `GET /health`

Unauthenticated liveness endpoint. It reports the configured Whisper model name and whether the model has loaded.

Example response:

```json
{"status":"ok","model":"small","loaded":true}
```

This endpoint does not check Tesseract or DjVuLibre. Use `/ready` for that diagnostic.

## `GET /ready`

Requires `DOCUMENT_API_KEY` in `Authorization: Bearer <key>`. Reports whether Tesseract is installed, which language data it can see, whether all required DjVuLibre programs are on `PATH`, and whether the Whisper model is loaded.

Example response (actual booleans/languages depend on the host):

```json
{"tesseract":true,"languages":["eng","osd","rus"],"djvulibre":true,"model_loaded":true}
```

An absent tool or language is reported as a diagnostic value; the endpoint does not install packages. A missing or invalid key returns `401`.

## `POST /transcribe`

Recognizes an audio file. Authentication key: `WHISPER_API_KEY`.

Request:

```bash
curl -X POST \
  -H "Authorization: Bearer <WHISPER_API_KEY>" \
  -F "file=@voice.ogg" \
  http://HOST:8000/transcribe
```

Response `200`:

```json
{"text":"recognized text","language":"ru","duration":12.3}
```

| Status | Meaning |
|---:|---|
| 400 | Audio is unreadable or exceeds `MAX_AUDIO_DURATION` |
| 401 | Missing or invalid Whisper key |
| 413 | Upload exceeds `MAX_AUDIO_SIZE` or request-body limit |
| 503 | Whisper model is not loaded or the bounded work queue is full (`Retry-After: 30` for a full queue) |
| 500 | Unexpected internal failure; implementation details are not returned |

## `POST /process-document`

Extracts text from a supported document. Authentication key: `DOCUMENT_API_KEY`.

Request without the optional text budget:

```bash
curl -X POST \
  -H "Authorization: Bearer <DOCUMENT_API_KEY>" \
  -F "file=@document.pdf" \
  http://HOST:8000/process-document
```

Optional multipart field `max_characters` is an integer between 1 and the server maximum. It can only reduce extraction work; it cannot raise the configured server limit. Old clients that omit this field continue to work.

```bash
curl -X POST \
  -H "Authorization: Bearer <DOCUMENT_API_KEY>" \
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
|---:|---|
| 400 | Empty, corrupt, prohibited XML, or unsupported document |
| 401 | Missing or invalid document key |
| 413 | Document upload exceeds 50 MiB or request-body limit |
| 503 | A required native dependency is missing, or the bounded work queue is full (`Retry-After: 30` for a full queue) |
| 504 | `DOCUMENT_PROCESSING_TIMEOUT` elapsed |
| 500 | Unexpected internal failure; implementation details are not returned |

### Supported formats

PDF (OCR for pages without a text layer), DOCX, XLSX, PPTX, ODT, ODS, ODP, EPUB, FB2, DJVU (OCR for scanned pages), TXT, MD, RTF, HTML, XML, CSV.

Unsupported: legacy Office binary formats `.doc`, `.xls`, `.ppt`, and standalone image files. Image, animation, and video processing are outside this service.

## Optional correlation header: `X-Request-ID`

A client may send an identifier containing 8–64 ASCII letters, digits, dots, underscores, or hyphens. The backend validates it, generates a UUID when absent/invalid, echoes it in the response header, and includes it in log records. Do not put personal data or secrets in this value.

## Authentication and compatibility

- `/health` is intentionally unauthenticated.
- `/ready` and `/process-document` use `DOCUMENT_API_KEY`.
- `/transcribe` uses `WHISPER_API_KEY`.
- `ALLOW_UNAUTHENTICATED=true` is only for isolated local development and must remain `false` in production.
- The bot's established paths, multipart field `file`, and required successful response fields remain unchanged.
