# Security checklist before production

Complete this checklist on the actual machines A (bot) and B (backend/LLM). The addresses below are examples from the deployment plan (`10.8.0.1` for B, `10.8.0.2` for A); replace them with the real private/VPN addresses. Do not enable a firewall until the administrator's SSH source has an explicit allow rule. Start on a test machine.

| # | Check | How to verify | Expected |
|---:|---|---|---|
| 1 | Services bind only to private addresses | B: `ss -tlnp \| grep -E ':8000\|:8080'` | `10.8.0.1` or `127.0.0.1`; not `0.0.0.0` or `*` |
| 2 | Other machines cannot reach service ports | From a third machine: `curl -m 3 http://10.8.0.1:8000/health` | No connection |
| 3 | Firewall is enabled and restrictive | B: `sudo ufw status verbose` | Incoming denied except bot/admin/VPN allowances |
| 4 | A-to-B channel is encrypted | `sudo wg show` or verify HTTPS certificate chain | Recent WireGuard handshake or trusted TLS |
| 5 | No document access without key | `curl -i -F file=@a.txt http://10.8.0.1:8000/process-document` | `401` |
| 6 | Document access works with correct key | Repeat with `Authorization: Bearer <key>` | `200` |
| 7 | Each service has a different key | Compare protected `.env` files on A and B without displaying values | Keys differ |
| 8 | Environment file permissions are restricted | `stat -c '%a %U %n' .env` on A and B | `600` or service-group `640` |
| 9 | Secrets are absent from command-line arguments | `ps aux \| grep -E 'api-key\|uvicorn\|llama'` | No API key/token values |
| 10 | Backend runs without root | `ps -o user= -C uvicorn` | Dedicated `mediabackend` account |
| 11 | Service cannot modify backend code | `sudo -u mediabackend touch /opt/media-backend/app.py` | `Permission denied` |
| 12 | Backend has no unrestricted internet egress | `sudo -u mediabackend curl -m 3 https://example.org` or inspect `IPAddressDeny` | No connection |
| 13 | Whisper loads without network | Disconnect external network on B and restart service | Service starts; `/health` returns `loaded: true` |
| 14 | Resource limits are active | `systemctl show media-backend -p MemoryMax -p CPUQuotaPerSecUSec` | Values are set |
| 15 | systemd sandbox reviewed | `systemd-analyze security media-backend.service` | Findings reviewed and accepted |
| 16 | API docs are disabled | `curl -i http://10.8.0.1:8000/docs` with `ENABLE_DOCS=false` | `404` |
| 17 | Logs contain no secrets or user content | Inspect `journalctl -u media-backend`; search for `Bearer`, tokens, and a test phrase | No secret or uploaded content |
| 18 | Oversized upload is rejected | Upload a file exceeding the configured limit | Fast `413` |
| 19 | Queue overload returns 503 | Send 10 document requests concurrently | Excess work is rejected with `503`, service stays responsive |
| 20 | Code integrity baseline matches | `sha256sum -c --quiet /root/media-backend.baseline.sha256` | No output / exit code 0 |
| 21 | Data and backups are encrypted | Review LUKS and backup encryption configuration | Encryption enabled |
| 22 | Host clocks are synchronized | `timedatectl status` on A and B | `System clock synchronized: yes` |
| 23 | Bot allow-list policy is restrictive | Inspect bot `.env`: `ALLOW_ALL_USERS=false`, `ALLOWED_USERS` populated | Only intended users have access |
| 24 | Key rotation and incident procedure are understood | Rehearse D.2.3 with test keys and review D.7 | Procedure works without exposing production secrets |

This checklist is not an automated certification. Record the date, host, operator, exceptions, and evidence in your operations records. Re-run it after network, systemd, key, or dependency changes.
