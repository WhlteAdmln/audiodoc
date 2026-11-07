# Connecting the Telegram bot to audiodoc

This guide connects `bot-obormot` to `audiodoc`. The bot sends audio and documents to audiodoc over HTTP; text chat goes directly from the bot to the OpenAI-compatible LLM server. Image, GIF, sticker, and video handling remains in the bot.

Related documentation: [audiodoc API](api.md), [deployment examples](../deploy/README.md), [bot repository](https://github.com/WhlteAdmln/bot-obormot), and the bot's [configuration guide](https://github.com/WhlteAdmln/bot-obormot#connecting-to-audiodoc).

## 1. Components and request flow

```text
Telegram
   |
   v
bot-obormot (machine A)
   |-- text ------------------------> LLM server: POST /v1/chat/completions
   |-- voice/audio, multipart file -> audiodoc: POST /transcribe
   |-- document, multipart file ----> audiodoc: POST /process-document
   |
   +-- conversation history -------> local SQLite

Machine B normally hosts both audiodoc and the LLM server.
```

The bot must be able to reach the full endpoint URLs. It does not append `/transcribe` or `/process-document` automatically.

## 2. Settings correspondence

| Purpose | `bot-obormot` | `audiodoc` | Notes |
| --- | --- | --- | --- |
| Transcription URL | `WHISPER_API_URL` | Uvicorn host/port | Full URL, including `/transcribe` |
| Document URL | `DOCUMENT_API_URL` | Uvicorn host/port | Full URL, including `/process-document` |
| Transcription key | `WHISPER_API_KEY` | `WHISPER_API_KEY` | Values must match |
| Document key | `DOCUMENT_API_KEY` | `DOCUMENT_API_KEY` | Values must match and differ from the transcription key |
| Key rotation | One active key | Comma-separated accepted keys | Enables overlap during rotation |
| Upload field | `file` | `file` | `multipart/form-data` |
| Transcription response | Reads `text` | `{text, language, duration}` | All three fields are part of the response contract |
| Document response | Validates `format`, `text`, `characters`; handles `truncated` | `{format, text, characters, truncated}` | `truncated=true` is reported to the user as an oversized document |

`GET /health` is unauthenticated. `GET /ready` and `POST /process-document` use `DOCUMENT_API_KEY`; `POST /transcribe` uses `WHISPER_API_KEY`. Keep the two keys different. In production, keep `ALLOW_UNAUTHENTICATED=false`.

## 3. Effective limits

| Limit | Bot | audiodoc | Effective behavior |
| --- | ---: | ---: | --- |
| Uploaded file size | 20 MiB | Audio 25 MiB; document 50 MiB | The bot's 20 MiB limit is stricter for both upload types |
| Audio duration | 300 s | 600 s | The bot rejects audio over 5 minutes before sending it |
| Text passed to the LLM | 12,288 characters | Up to 2,000,000 characters by default | The bot asks audiodoc for at most 11,264 characters, reserving 1,024 for labels, filename, and caption |
| Request timeout | Audio 180 s; document 300 s | Document processing deadline 180 s | Queue waiting is also part of the bot's request time; tune for your load |
| Waiting queue | — | 4 waiting transcription jobs; 4 waiting document jobs | A full queue returns `503` with `Retry-After: 30` |
| Active document processing | — | 2 workers | CPU, RAM, disk, and OCR cost determine throughput |
| Active transcription | — | 1 worker by default | Whisper can compete with the LLM for CPU/GPU resources |

The bot sends the document `max_characters=11264` multipart field. This reduces extraction work on audiodoc and leaves room for the bot's document label, filename, and an optional Telegram caption. Do not raise this value beyond the bot's input limit without changing and testing the bot's own validation.

## 4. Choose a network layout

### Scenario 1 — both services on one machine

This is the simplest setup for a local test. Run audiodoc, the LLM server, and the bot on the same host.

`audiodoc/.env`:

```ini
WHISPER_API_KEY=REPLACE_WITH_RANDOM_KEY_1
DOCUMENT_API_KEY=REPLACE_WITH_RANDOM_KEY_2
ALLOW_UNAUTHENTICATED=false
```

Start audiodoc from its project root:

```bash
uvicorn app:app --host 127.0.0.1 --port 8000
```

`bot-obormot/.env`:

```ini
LLM_BASE_URL=http://127.0.0.1:8080/v1
WHISPER_API_URL=http://127.0.0.1:8000/transcribe
WHISPER_API_KEY=REPLACE_WITH_RANDOM_KEY_1
DOCUMENT_API_URL=http://127.0.0.1:8000/process-document
DOCUMENT_API_KEY=REPLACE_WITH_RANDOM_KEY_2
```

Replace the two key placeholders with different random values. The corresponding values in the bot and audiodoc must match.

### Scenario 2 — two machines over WireGuard (recommended layout)

The deployment examples use machine A (bot) at `10.8.0.2` and machine B (audiodoc plus LLM) at `10.8.0.1`. These are examples; replace them if your WireGuard addresses differ.

On machine B, bind audiodoc to its private VPN address:

```bash
uvicorn app:app --host 10.8.0.1 --port 8000
```

Allow inbound TCP ports `8000` (audiodoc) and `8080` (LLM) only from the bot's VPN address `10.8.0.2`. Review [`deploy/README.md`](../deploy/README.md) and `deploy/ufw-rules.sh.example` before applying firewall changes. Do not expose either service to the public internet.

`bot-obormot/.env` on machine A:

```ini
LLM_BASE_URL=http://10.8.0.1:8080/v1
WHISPER_API_URL=http://10.8.0.1:8000/transcribe
WHISPER_API_KEY=REPLACE_WITH_RANDOM_KEY_1
DOCUMENT_API_URL=http://10.8.0.1:8000/process-document
DOCUMENT_API_KEY=REPLACE_WITH_RANDOM_KEY_2
```

Use the same two key values in `audiodoc/.env` on machine B. Plain HTTP inside WireGuard is acceptable because the VPN tunnel encrypts traffic between the peers.

### Scenario 3 — HTTPS through nginx instead of WireGuard

Keep Uvicorn bound to loopback on machine B and let nginx terminate TLS. Configure the nginx source-IP allow-list for the bot host and use a certificate trusted by the bot's operating system/Python environment.

```ini
WHISPER_API_URL=https://backend.example.internal/transcribe
DOCUMENT_API_URL=https://backend.example.internal/process-document
```

Keep the same matching Bearer keys as configured in audiodoc. Do not disable certificate verification in the bot. The LLM server must also use a protected channel or private network; do not expose it directly to the internet.

### Resource note

The LLM and Whisper can compete for CPU, RAM, and GPU memory when they share machine B. audiodoc defaults to CPU inference (`WHISPER_DEVICE=cpu`). If you move Whisper to a GPU, account for the LLM's VRAM needs and tune the systemd resource controls in the deployment example.

## 5. Verify the connection

Run these commands from machine A (the bot host), not only from machine B. That verifies routing and firewall rules as well as the services. The examples below assume the WireGuard scenario; replace the host for your layout.

Set keys in the current shell for the test session. Do not paste real keys into tickets, logs, or shared terminal recordings:

```bash
export DOCUMENT_API_KEY='your-document-key'
export WHISPER_API_KEY='your-whisper-key'
```

1. Liveness, no key required. After the model loads, expect `loaded: true`:

```bash
curl -fsS http://10.8.0.1:8000/health
```

1. Document dependencies, document key required. Expect booleans and installed language codes:

```bash
curl -fsS http://10.8.0.1:8000/ready \
  -H "Authorization: Bearer ${DOCUMENT_API_KEY}"
```

1. Document extraction. Expect `format`, `text`, `characters`, and `truncated`:

```bash
echo 'Example document text.' > /tmp/audiodoc-sample.txt
curl -fsS \
  -H "Authorization: Bearer ${DOCUMENT_API_KEY}" \
  -F "file=@/tmp/audiodoc-sample.txt" \
  -F "max_characters=11264" \
  http://10.8.0.1:8000/process-document
```

1. Transcription. Use a short valid `.ogg` file and expect `text`, `language`, and `duration`:

```bash
curl -fsS \
  -H "Authorization: Bearer ${WHISPER_API_KEY}" \
  -F "file=@voice.ogg" \
  http://10.8.0.1:8000/transcribe
```

Finally, send a short voice message and a small `.txt` document to the Telegram bot. Successful direct `curl` requests do not replace this end-to-end check.

## 6. Rotate keys without an authentication gap

The audiodoc API accepts multiple comma-separated active keys. Rotate each endpoint key independently:

1. In `audiodoc/.env`, set the endpoint key to `OLD_KEY,NEW_KEY`, then restart audiodoc. Both keys are accepted during the transition.
2. Update the matching key in the bot's `.env`, then restart the bot.
3. After confirming requests succeed, remove `OLD_KEY` from audiodoc's `.env` and restart audiodoc again.

Do not combine the Whisper and document keys; they protect different endpoints.

## 7. Troubleshooting

| Symptom | Likely cause | What to check |
| --- | --- | --- |
| Bot cannot connect to the service | Wrong host/port, service stopped, firewall blocks traffic, or Uvicorn listens only on loopback | Call `/health` from machine A; inspect `ss -tlnp` and UFW rules on B |
| HTTP `404` | URL is missing the endpoint path | Include `/transcribe` or `/process-document` in the bot URL |
| HTTP `401` | Key mismatch or wrong key group | Compare the bot's Whisper key with `WHISPER_API_KEY`, and its document key with `DOCUMENT_API_KEY` without sharing secret values |
| HTTP `503` | Whisper is not loaded or a bounded queue is full | Check `/health`, service logs, and `Retry-After`; reduce load or tune queue limits carefully |
| HTTP `413` | Upload exceeds the bot or server limit | Check the 20 MiB bot limit and audiodoc's 25/50 MiB endpoint limits |
| HTTP `400` for audio | Audio is invalid or longer than the configured server limit | The bot currently rejects audio over 300 seconds; audiodoc defaults to 600 seconds |
| HTTP `504` or bot timeout | Document deadline or client timeout elapsed; queue wait may contribute | Inspect backend logs and load before increasing timeouts |
| First startup appears slow | Whisper model is being downloaded or loaded | Pre-download a model, set `WHISPER_MODEL_PATH`, and use `WHISPER_OFFLINE=true` when ready |

For endpoint details and status codes, see [the API reference](api.md). For host hardening and network setup, see [deployment examples](../deploy/README.md).
