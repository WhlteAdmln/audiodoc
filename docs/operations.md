# Operations guide

This document describes a conservative, single-service deployment. Adapt paths, addresses, resource caps, and network policy to the actual host. Test changes before applying them to the working service.

## Production deployment

This section is the canonical production-deployment guide. The files under `deploy/` are templates, not drop-in configurations. The examples assume machine A (the bot) uses WireGuard address `10.8.0.2` and machine B (audiodoc and the LLM) uses `10.8.0.1`; backend TCP `8000`, LLM TCP `8080`, and WireGuard UDP `51820` are examples only. Replace every address, path, username, resource limit, certificate path, and allowed SSH source address before use. No real secret is included in the templates.

### Dedicated service account and filesystem

The example installs the release and virtual environment under `/opt/audiodoc`, owned by root, with read access for the `audiodoc` service group. Copy the reviewed release, virtual environment, model directory, and protected `.env` before applying ownership changes:

```bash
sudo useradd --system --home /opt/audiodoc --shell /usr/sbin/nologin audiodoc
sudo mkdir -p /opt/audiodoc/tmp
sudo chown -R root:audiodoc /opt/audiodoc
sudo chmod -R g-w,o-rwx /opt/audiodoc
sudo chown audiodoc:audiodoc /opt/audiodoc/tmp
sudo chmod 700 /opt/audiodoc/tmp
sudo chown root:audiodoc /opt/audiodoc/.env
sudo chmod 640 /opt/audiodoc/.env
```

The service account can read code, the virtual environment, model files, and `.env`, but cannot modify them. It can write only to `tmp/`. Check ownership and modes after copying files: recursive commands can affect more files than intended when run from the wrong directory. For a manually managed single-user service, use `chmod 600 .env` instead.

### systemd service

The canonical unit is rendered by `audiodoc service install`; `deploy/audiodoc.service.example` is a template. For system mode, keep `AUDIODOC_HOME` outside `/home` (for example, `/opt/audiodoc`) because the hardened unit uses `ProtectHome=true`. The `audiodoc` service account must be able to read the release and `.env`, and write to `tmp/`.

Preview and install the hardened unit:

```bash
AUDIODOC_HOME=/opt/audiodoc /opt/audiodoc/.venv/bin/audiodoc service install --system --print
sudo env AUDIODOC_HOME=/opt/audiodoc /opt/audiodoc/.venv/bin/audiodoc service install --system
```

The install command does not reload systemd, enable, or start the service. Review the generated unit, then run the following commands deliberately:

```bash
sudo systemd-analyze verify /etc/systemd/system/audiodoc.service
sudo systemctl daemon-reload
sudo systemctl enable --now audiodoc.service
sudo systemctl status audiodoc.service
sudo journalctl -u audiodoc.service -n 100 --no-pager
```

The hardened unit denies network access except the configured private subnet and loopback. Defaults include `IPAddressAllow=10.8.0.0/24 127.0.0.1`, `MemoryHigh=10G`, and `MemoryMax=12G`; the unit renderer accepts these as parameters. `IPAddressDeny` and `IPAddressAllow` require a compatible Linux/systemd/cgroup environment. For NVIDIA GPU inference, review whether a narrow `DeviceAllow=` and `PrivateDevices=false` are required.

### UFW firewall

The [example UFW script](../deploy/ufw-rules.sh.example) sets incoming traffic to deny and outgoing traffic to allow, permits backend and LLM ports only from the bot's VPN address, and permits SSH only from an explicit administrator address. With WireGuard, it can also permit UDP `51820` only from the bot's public endpoint.

**Before running the script:** establish a second SSH session or console access, set `ADMIN_SSH_IP`, and verify the source address. A wrong rule can lock you out. Review the script before using `sudo`:

```bash
sed -n '1,200p' deploy/ufw-rules.sh.example
ADMIN_SSH_IP=203.0.113.25 BOT_VPN_IP=10.8.0.2 sudo -E sh deploy/ufw-rules.sh.example
sudo ufw status verbose
```

For WireGuard, also set `BOT_WG_PUBLIC_IP` to the bot machine's public source address. If that address changes, update the firewall rule deliberately.

### WireGuard

Generate a different private/public key pair on each machine. On each host:

```bash
umask 077
wg genkey | tee privatekey | wg pubkey > publickey
```

Place each private key only in that host's protected `/etc/wireguard/wg0.conf`, replacing the matching placeholder in the corresponding template. Exchange only public keys. Set the backend's public endpoint in the bot peer configuration, then secure and start the final config:

```bash
sudo chown root:root /etc/wireguard/wg0.conf
sudo chmod 600 /etc/wireguard/wg0.conf
sudo wg-quick up wg0
sudo systemctl enable wg-quick@wg0
sudo wg show
```

The WireGuard UDP port must be reachable from the bot endpoint. Keep backend TCP ports `8000` and `8080` private to the VPN. The bot's backend URL uses `http://10.8.0.1:8000`; the LLM URL uses `http://10.8.0.1:8080`.

### nginx HTTPS alternative

Use `deploy/nginx.conf.example` only when choosing TLS termination instead of WireGuard. Set the real DNS name, certificate paths, and source-IP allow-list. Keep Uvicorn bound to `127.0.0.1:8000`; do not also expose port `8000` to the network. Do not disable certificate validation in the bot. If the bot supplies `X-Request-ID`, nginx forwards it; otherwise nginx supplies its own request ID for the backend.

### Integrity baseline

After installing a trusted release, create a baseline outside the writable service tree:

```bash
cd /opt/audiodoc
sudo find audiodoc app.py -type f -name '*.py' -exec sha256sum {} + | sudo tee /root/audiodoc.baseline.sha256 >/dev/null
```

Check it periodically:

```bash
cd /opt/audiodoc
sudo sha256sum -c --quiet /root/audiodoc.baseline.sha256
```

Recreate the baseline only after a reviewed deployment or update. Do not overwrite it automatically after a failed integrity check.

### Secret handling

Use different, randomly generated keys for Whisper and documents. Never put private keys or application keys into example files, archives, command-line options, or logs. For the backend `.env`, use mode `640` with ownership `root:audiodoc` in this service template; use `600` when only the owning service/admin account needs access. Keep the bot and backend values synchronized and use the rotation procedure in the [bot connection guide](connecting-the-bot.md). Review the [security checklist](security-checklist.md) before production activation.

## 1. Operating-system dependencies

Install the system packages required by the document extraction engines. On Debian/Ubuntu:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip tesseract-ocr tesseract-ocr-rus tesseract-ocr-eng djvulibre-bin
```

Tesseract language data must include `rus` and `eng` when those languages are expected. DjVu support requires DjVuLibre tools. Keep OS packages updated through the host's normal security-update process.

## 2. Environment file and permissions

Keep the application `.env` readable only by the account that needs it. For a manually managed service user:

```bash
chmod 600 .env
```

For the dedicated system-service layout, use the ownership and file modes in [Production deployment](#production-deployment) (`root:audiodoc`, mode `640`). The application sets `umask(077)` and creates its configured temp directory with restrictive permissions. The temp directory should be writable only by the service account (`chmod 700`).

Keep `AUDIODOC_AUDIO_KEY` and `AUDIODOC_DOCUMENT_KEY` different, long, and random. Do not enable `ALLOW_UNAUTHENTICATED` on a server. Configuration names, defaults, and examples are listed in [the configuration reference](configuration.md).

## 3. Whisper model and offline startup

The first startup may download the selected Whisper model. On a host without unrestricted internet access, download or copy the model during a controlled preparation step, set `WHISPER_MODEL_PATH` to the local model directory, and set `WHISPER_OFFLINE=true` after confirming the files are present.

For example, the relevant `.env` settings may look like:

```ini
WHISPER_MODEL_PATH=/opt/audiodoc/models/whisper-small
WHISPER_OFFLINE=true
```

The model directory must be readable by the service account. Do not set offline mode before the model files have been provisioned. For CPU deployments, start with `WHISPER_DEVICE=cpu` and `WHISPER_COMPUTE_TYPE=int8`; tune thread count and model size after observing actual load. GPU settings depend on the installed CUDA runtime and available device memory.

## 4. Start and stop

For a user-level systemd service:

```bash
systemctl --user daemon-reload
systemctl --user enable --now audiodoc.service
systemctl --user status audiodoc.service
```

To inspect logs and stop or restart it:

```bash
journalctl --user -u audiodoc.service -n 100 --no-pager
systemctl --user restart audiodoc.service
systemctl --user stop audiodoc.service
```

For the system-wide unit installed using the production guide, use `sudo systemctl` instead of `systemctl --user`. Do not run two audiodoc instances against the same temp directory or port. When starting manually for development, run the command from the application environment and bind to loopback unless the network layout explicitly requires a private interface:

```bash
uvicorn app:app --host 127.0.0.1 --port 8000
```

The release installer supports reviewing the installer before execution. Do not pipe an unreviewed remote script directly into a shell:

```bash
curl -fsSLo install.sh https://raw.githubusercontent.com/WhlteAdmln/audiodoc/main/install.sh
less install.sh
sh install.sh --help
```

The installer can verify a published `SHA256SUMS` entry for the release archive when one is attached to the GitHub Release; if the release has no checksum asset (or only GitHub's generated source ZIP), it reports that independent archive verification was unavailable. For production hardening with a dedicated system account and system-wide systemd unit, use [Production deployment](#production-deployment) above.

## 5. Health and readiness

`GET /health` is a liveness check and does not require authentication. It reports whether the application is running and whether the Whisper model is loaded. `GET /ready` checks document-processing dependencies and requires the document Bearer key:

```bash
curl -i http://127.0.0.1:8000/health
curl -i http://127.0.0.1:8000/ready \
  -H "Authorization: Bearer $AUDIODOC_DOCUMENT_KEY"
```

A healthy process is not necessarily ready to transcribe if the model is still loading. A readiness failure for OCR or DJVU usually means a system package or language-data package is missing. Keep `/docs` and `/openapi.json` disabled in production unless there is a specific operational reason to expose them (`ENABLE_DOCS=false` by default).

## 6. Logs and request tracing

For a system service, inspect recent logs with:

```bash
sudo journalctl -u audiodoc.service -n 100 --no-pager
sudo journalctl -u audiodoc.service -f
```

For a user service, use `journalctl --user -u audiodoc.service`. Set `LOG_LEVEL=INFO` for normal operations; use `DEBUG` only during a controlled investigation, then return to `INFO` or a less verbose level.

The service accepts `X-Request-ID` and includes the request identifier in its logs and response headers. Pass the same identifier through the bot/proxy chain when possible. Avoid logging Authorization headers, API keys, full document contents, or private uploaded files. Redact secrets before sharing diagnostic output.

## 7. Troubleshooting

| Symptom | Checks |
| --- | --- |
| Service does not start | Check `.env` syntax and permissions, the selected Python environment, `journalctl`, and whether the port is already occupied. |
| `/health` reports the model is not loaded | Check model download/provisioning, `WHISPER_MODEL_PATH`, disk space, and whether offline mode was enabled too early. |
| `/ready` reports a missing OCR language | Install the matching Tesseract language package and verify `tesseract --list-langs`. |
| DJVU extraction fails | Install DjVuLibre and verify `ddjvu`/`djvutxt` are available on `PATH`. |
| Requests return `401` | Check that the endpoint uses the correct key: audio key for `/transcribe`, document key for `/process-document` and `/ready`. |
| Requests return `413` | Check the endpoint's configured upload limit and the reverse proxy's body-size limit. |
| Requests return `503` | Whisper may still be loading or the bounded work queue may be full. Inspect logs and retry after the advertised `Retry-After` interval. |
| Requests time out | Check CPU/GPU contention, queue wait, OCR input size, and client/proxy deadlines before increasing limits. |

## 8. Dependency maintenance

- Install OS security updates regularly, especially Tesseract, DjVuLibre, and image libraries.
- For Python dependency updates, create a new virtual environment from the reviewed lock file, run unit and integration tests, switch the service only after tests pass, and retain the old environment for rollback.
- Run `pip-audit -r requirements-lock.txt` periodically on a machine with package-index access. Review the findings; do not blindly upgrade parser libraries directly on production.
- After changing the deployed code, regenerate the integrity baseline described in [Production deployment](#production-deployment) and verify it periodically.

<!-- TODO: Remove this compatibility section after release 0.2.0. -->
## 9. Migrating from previous deployment names

The compatibility period supports installations that still use the previous application home, service account, or deployment names. Do not rename a live service directory or systemd unit by copying example files over it. First back up the current service definition, `.env`, model directory, temporary data that must be retained, and the existing virtual environment. Record the current `ExecStart`, owner/group, file permissions, bind address, and port.

Use the current installer or `audiodoc service install` output to identify the new paths and unit definition. Review the generated configuration before replacing the live unit. Keep the old environment and service definition until the new service passes `audiodoc doctor`, `/health`, `/ready`, and an end-to-end bot request. The installer restores moved source files and a saved user unit if its migration doctor check fails, but it does not roll back an existing virtual environment or modify system-wide systemd units. Operators with a hand-written system unit should change `ExecStart` to `<AUDIODOC_HOME>/.venv/bin/audiodoc run`; the old `uvicorn app:app` command remains compatible for one release because the wheel ships `app.py`.

## 10. Safe rollback

Keep the previous release, virtual environment, and service definition available until the upgraded service is verified. To roll back, stop the service, restore the prior application files and unit definition from the backup, verify `.env` ownership and permissions, reload systemd, and restart the prior unit. Do not restore a stale `.env` over a newer one without checking key rotations and configuration changes.

After rollback, check `/health`, `/ready`, and one representative audio and document request from the bot host. Preserve the failed release and its logs for diagnosis; do not delete the only copy before identifying the cause.

## 11. Upgrading from 0.1.0

The `0.1.0` deployment may have run directly from `backend/main.py` or an older project directory. Back up `.env`, the model directory, temporary files that must be retained, and the existing service definition before upgrading. Use the reviewed release installer in upgrade mode:

```bash
sh install.sh --upgrade
```

The upgrade keeps the existing application home and virtual environment available for recovery and places legacy files in the `AUDIODOC_HOME` migration backup directory when applicable. Review the install output, then run:

```bash
audiodoc doctor --offline
systemctl --user daemon-reload
systemctl --user restart audiodoc.service
```

If the service is system-wide, use the corresponding `sudo systemctl` commands. Confirm the active `ExecStart`, `/health`, `/ready`, and a real bot request before removing any backup. The installer does not rewrite arbitrary hand-maintained system units; review their paths explicitly.
