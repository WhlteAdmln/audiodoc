# Deployment examples

These files are **templates**, not drop-in production configuration. They follow the example topology from the refactoring plan:

- Machine A (bot): WireGuard address `10.8.0.2`.
- Machine B (backend and LLM): WireGuard address `10.8.0.1`.
- Backend: TCP `8000`; LLM: TCP `8080`; WireGuard: UDP `51820`.

Replace all example addresses, external endpoints, paths, usernames, resource limits, certificate paths, and allowed SSH source addresses before applying anything. No private key, API key, bot token, or other real secret is included in these examples.

If a live host still uses the former service/account/directory names, do not rename them just by copying these examples. Read the migration guidance in [`docs/operations.md`](../docs/operations.md#migrating-from-previous-deployment-names) first.

## 1. Dedicated service account and filesystem

Example assumes the code and virtual environment are installed under `/opt/audiodoc`, owned by root, with group-readable access for the `audiodoc` service:

```bash
sudo useradd --system --home /opt/audiodoc --shell /usr/sbin/nologin audiodoc
sudo mkdir -p /opt/audiodoc/tmp
# Copy the reviewed code, venv, model directory, and protected .env first.
sudo chown -R root:audiodoc /opt/audiodoc
sudo chmod -R g-w,o-rwx /opt/audiodoc
sudo chown audiodoc:audiodoc /opt/audiodoc/tmp
sudo chmod 700 /opt/audiodoc/tmp
sudo chown root:audiodoc /opt/audiodoc/.env
sudo chmod 640 /opt/audiodoc/.env
```

The service account can read code, the virtual environment, model files, and `.env`, but cannot modify them. It can write only to `tmp/`. Check these assumptions after copying files; recursive ownership and mode commands can affect more files than intended when run from the wrong path.

## 2. systemd service

1. Copy `audiodoc.service.example` to `/etc/systemd/system/audiodoc.service`.
2. Change `WorkingDirectory`, `EnvironmentFile`, `ExecStart`, private IP, `MemoryHigh`, `MemoryMax`, and `CPUQuota` to match your host.
3. Confirm the model path is readable and the temporary directory is writable by `audiodoc`.
4. Enable it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now audiodoc
systemctl status audiodoc
sudo journalctl -u audiodoc -n 100 --no-pager
systemd-analyze security audiodoc.service
```

The sample intentionally blocks service network egress except the private subnet and loopback. It assumes Whisper is local (`WHISPER_OFFLINE=true`) and runtime dependencies are installed. `IPAddressDeny`/`IPAddressAllow` require a compatible Linux/systemd/cgroup environment; verify that the properties are active. If Whisper uses an NVIDIA GPU, the default device sandbox may need deliberate adjustment (`PrivateDevices=false` and a narrow `DeviceAllow=` for the required GPU devices); review the security impact and your driver requirements first.

## 3. UFW firewall

The sample script sets incoming traffic to deny and outgoing traffic to allow, permits backend and LLM ports only from the bot's VPN address, and permits SSH only from an explicit administrator address. If WireGuard is used, it can also permit UDP 51820 only from the bot's public endpoint address.

**Before running the script:** establish a second SSH session or console access, set `ADMIN_SSH_IP`, and verify that it is the correct source address. A wrong rule can lock you out. Review the script before `sudo` execution:

```bash
sed -n '1,200p' ufw-rules.sh.example
ADMIN_SSH_IP=203.0.113.25 BOT_VPN_IP=10.8.0.2 sudo -E sh ufw-rules.sh.example
sudo ufw status verbose
```

For WireGuard also set `BOT_WG_PUBLIC_IP` to the bot machine's public source address. If the bot's public address changes, update the rule deliberately.

## 4. WireGuard

Generate a different private/public keypair on each machine. On each host:

```bash
umask 077
wg genkey | tee privatekey | wg pubkey > publickey
```

Place the private key only into the corresponding host's protected `/etc/wireguard/wg0.conf`, replacing the placeholder in the appropriate `.example` file. Exchange only public keys. Set the backend's public endpoint in the bot peer configuration. Secure the final configs:

```bash
sudo chown root:root /etc/wireguard/wg0.conf
sudo chmod 600 /etc/wireguard/wg0.conf
sudo wg-quick up wg0
sudo systemctl enable wg-quick@wg0
sudo wg show
```

WireGuard's UDP port must be reachable from the bot endpoint. Keep backend TCP ports 8000 and 8080 private to the VPN. Then set the bot API URLs to `http://10.8.0.1:8000/transcribe`, `http://10.8.0.1:8000/process-document`, and the LLM URL to `http://10.8.0.1:8080`.

## 5. nginx HTTPS alternative

Use `nginx.conf.example` only when choosing TLS termination instead of WireGuard. Set the real DNS name, certificate paths, and source-IP allow-list. Keep Uvicorn bound to `127.0.0.1:8000`; do not also expose port 8000 to the network. Do not disable certificate validation in the bot. If a request ID is supplied by the bot, nginx forwards it; if not, nginx supplies its own ID for the backend.

## 6. Integrity baseline

After installing a trusted release, create a baseline outside the writable service tree:

```bash
cd /opt/audiodoc
sudo find backend app.py -type f -name '*.py' -exec sha256sum {} + | sudo tee /root/audiodoc.baseline.sha256 >/dev/null
```

Check it periodically:

```bash
cd /opt/audiodoc
sudo sha256sum -c --quiet /root/audiodoc.baseline.sha256
```

Recreate the baseline only after a reviewed deployment or update. Do not overwrite it automatically on a failed integrity check.

## 7. Secret handling

Use different randomly generated keys for Whisper and documents. Never put private keys or application keys into these example files, archives, command-line options, or logs. For the backend `.env`, use mode `640` with `root:audiodoc` in this service template; use `600` when only the owning service/admin account needs access. See `docs/operations.md` and `docs/security-checklist.md` before production activation.
