#!/bin/sh
# audiodoc installer. Downloads a reviewed GitHub Release archive.
# Usage:
#   sh install.sh --latest
#   sh install.sh --nightly --systemd --host 10.8.0.1 --port 8000

set -eu
umask 077

APP_NAME="audiodoc"
DEFAULT_GITHUB_REPOSITORY="WhlteAdmln/audiodoc"
GITHUB_REPOSITORY="${AUDIODOC_GITHUB_REPOSITORY:-$DEFAULT_GITHUB_REPOSITORY}"
INSTALL_DIR="${AUDIODOC_INSTALL_DIR:-${HOME:-}/audiodoc}"
GITHUB_TOKEN="${GITHUB_TOKEN:-}"
CHANNEL="latest"
CHANNEL_WAS_SET=0
CREATE_SYSTEMD=0
HOST="127.0.0.1"
PORT="8000"
MODEL="small"
DEVICE="cpu"
COMPUTE_TYPE=""
COMPUTE_TYPE_WAS_SET=0
DOWNLOAD_MODEL=1
ASSUME_YES=0

log() {
	printf '%s\n' "[${APP_NAME}] $*"
}

warn() {
	printf '%s\n' "[${APP_NAME}] WARNING: $*" >&2
}

die() {
	printf '%s\n' "[${APP_NAME}] ERROR: $*" >&2
	exit 1
}

usage() {
	cat <<'EOF'
Usage: install.sh [options]

Release channel:
  --latest             Install the newest stable GitHub Release (default).
  --nightly            Install the newest GitHub prerelease.

Service:
  --systemd            Create a per-user systemd unit (not enabled or started).
  --host ADDR          Uvicorn bind address (default: 127.0.0.1).
  --port N             Uvicorn port (default: 8000).

Whisper:
  --model NAME         Model: tiny, base, small, medium, large-v3, etc. (default: small).
  --device cpu|cuda    Inference device (default: cpu).
  --compute-type TYPE  CTranslate2 compute type (default: int8 for cpu, float16 for cuda).
  --no-model           Do not download a model during installation.

Other:
  --yes                Do not ask interactive confirmation questions.
  --help               Show this help.

Optional environment variables:
  AUDIODOC_GITHUB_REPOSITORY  GitHub repository in owner/name format.
  AUDIODOC_INSTALL_DIR        Install directory (default: ~/audiodoc).
  GITHUB_TOKEN                Optional GitHub token for API rate limits.

The installer requires a Linux distribution with glibc and Python 3.11+.
Alpine Linux is not supported by this installer.
EOF
}

need_value() {
	[ "$#" -ge 2 ] || die "Option $1 requires a value. Use --help for usage."
	case "$2" in
	-* | '') die "Invalid value for $1: $2" ;;
	esac
}

while [ "$#" -gt 0 ]; do
	case "$1" in
	--latest)
		if [ "$CHANNEL_WAS_SET" -eq 1 ] && [ "$CHANNEL" != "latest" ]; then
			die "Use only one of --latest or --nightly."
		fi
		CHANNEL="latest"
		CHANNEL_WAS_SET=1
		;;
	--nightly)
		if [ "$CHANNEL_WAS_SET" -eq 1 ] && [ "$CHANNEL" != "nightly" ]; then
			die "Use only one of --latest or --nightly."
		fi
		CHANNEL="nightly"
		CHANNEL_WAS_SET=1
		;;
	--systemd)
		CREATE_SYSTEMD=1
		;;
	--host)
		need_value "$@"
		HOST="$2"
		shift
		;;
	--port)
		need_value "$@"
		PORT="$2"
		shift
		;;
	--model)
		need_value "$@"
		MODEL="$2"
		shift
		;;
	--device)
		need_value "$@"
		DEVICE="$2"
		shift
		;;
	--compute-type)
		need_value "$@"
		COMPUTE_TYPE="$2"
		COMPUTE_TYPE_WAS_SET=1
		shift
		;;
	--no-model)
		DOWNLOAD_MODEL=0
		;;
	--yes)
		ASSUME_YES=1
		;;
	--help | -h)
		usage
		exit 0
		;;
	*)
		die "Unknown argument: $1. Use --help for usage."
		;;
	esac
	shift
done

case "$GITHUB_REPOSITORY" in
/* | */ | */*/*)
	die "Invalid GitHub repository path: $GITHUB_REPOSITORY"
	;;
*[!A-Za-z0-9._/-]*)
	die "Invalid GitHub repository name: $GITHUB_REPOSITORY"
	;;
*/*) ;;
*) die "AUDIODOC_GITHUB_REPOSITORY must have owner/name format." ;;
esac

case "$HOST" in
'' | -* | *[!A-Za-z0-9.:-]*) die "Invalid host address: $HOST" ;;
esac
case "$PORT" in
'' | *[!0-9]*) die "Port must be an integer between 1 and 65535." ;;
esac
# awk avoids shell arithmetic overflow on an arbitrarily long port string.
awk -v port="$PORT" 'BEGIN { exit !(port >= 1 && port <= 65535 && int(port) == port) }' ||
	die "Port must be an integer between 1 and 65535."

case "$DEVICE" in
cpu | cuda) ;;
*) die "--device must be cpu or cuda." ;;
esac
case "$MODEL" in
	tiny | tiny.en | base | base.en | small | small.en | medium | medium.en | \
	large | large-v1 | large-v2 | large-v3 | large-v3-turbo | turbo | \
	distil-small.en | distil-medium.en | distil-large-v2 | distil-large-v3) ;;
*) die "Unsupported Whisper model name: $MODEL. See --help and faster-whisper model names." ;;
esac
if [ "$COMPUTE_TYPE_WAS_SET" -eq 0 ]; then
	if [ "$DEVICE" = "cuda" ]; then
		COMPUTE_TYPE="float16"
	else
		COMPUTE_TYPE="int8"
	fi
fi
case "$COMPUTE_TYPE" in
'' | *[!A-Za-z0-9_-]*) die "Invalid compute type: $COMPUTE_TYPE" ;;
esac

if [ "$(id -u)" -eq 0 ]; then
	die "Run this installer as a regular user, not root. It uses sudo only for OS packages."
fi

if [ -z "${HOME:-}" ] || [ ! -d "$HOME" ]; then
	die "HOME is not set to an existing directory."
fi

if command -v apk >/dev/null 2>&1; then
	die "Alpine Linux is not supported: this application depends on packages with glibc-compatible wheels (including CTranslate2). Use Debian, Ubuntu, Fedora, Arch, or openSUSE."
fi

if [ "$HOST" = "0.0.0.0" ] || [ "$HOST" = "::" ]; then
	warn "Binding to $HOST exposes Uvicorn on all network interfaces. Configure the host firewall before allowing network access."
	if [ "$ASSUME_YES" -ne 1 ]; then
		printf 'Continue with this public bind address? [y/N] ' >/dev/tty 2>/dev/null ||
			die "No interactive terminal is available. Use --yes only after reviewing the firewall configuration."
		IFS= read -r reply </dev/tty || reply=""
		case "$reply" in
		y | Y | yes | YES) ;;
		*) die "Installation cancelled." ;;
		esac
	fi
fi

RUNNING_USER=$(id -un)
if [ "$CREATE_SYSTEMD" -eq 1 ]; then
	command -v systemctl >/dev/null 2>&1 || die "--systemd was requested, but systemctl is not installed."
	systemctl --user show-environment >/dev/null 2>&1 ||
		die "The user systemd manager is unavailable. Log in through a systemd user session and retry."
	SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
	SYSTEMD_UNIT_FILE="$SYSTEMD_USER_DIR/audiodoc.service"
	if [ -e "$SYSTEMD_UNIT_FILE" ]; then
		die "The user systemd unit already exists: $SYSTEMD_UNIT_FILE. Remove or rename it before reinstalling."
	fi
fi

have() {
	command -v "$1" >/dev/null 2>&1
}

find_python() {
	PYTHON_BIN=""
	for candidate in python3.14 python3.13 python3.12 python3.11 python3; do
		if have "$candidate"; then
			candidate_path=$(command -v "$candidate")
			if "$candidate_path" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1; then
				PYTHON_BIN="$candidate_path"
				return 0
			fi
		fi
	done
	return 1
}

venv_works() {
	[ -n "$PYTHON_BIN" ] || return 1
	probe_dir=$(mktemp -d "${TMPDIR:-/tmp}/audiodoc-venv-check.XXXXXX") || return 1
	if "$PYTHON_BIN" -m venv "$probe_dir/venv" >/dev/null 2>&1 &&
		"$probe_dir/venv/bin/python" -m pip --version >/dev/null 2>&1; then
		venv_result=0
	else
		venv_result=1
	fi
	rm -rf "$probe_dir"
	return "$venv_result"
}

run_privileged() {
	if have sudo; then
		sudo "$@"
	else
		die "Missing OS packages and sudo is unavailable. Install the packages manually, then rerun this installer."
	fi
}

check_native_tools() {
	missing=0
	for program in tesseract djvutxt djvused ddjvu; do
		have "$program" || missing=1
	done
	if have tesseract; then
		languages=$(tesseract --list-langs 2>/dev/null || true)
		printf '%s\n' "$languages" | grep -qx 'rus' || missing=1
		printf '%s\n' "$languages" | grep -qx 'eng' || missing=1
	else
		missing=1
	fi
	return "$missing"
}

install_os_packages() {
	if have apt-get; then
		log "Installing OS packages with apt-get."
		run_privileged apt-get update
		run_privileged apt-get install -y --no-install-recommends \
			ca-certificates curl unzip python3 python3-venv python3-pip \
			tesseract-ocr tesseract-ocr-rus tesseract-ocr-eng djvulibre-bin
	elif have dnf; then
		log "Installing OS packages with dnf."
		run_privileged dnf install -y \
			ca-certificates curl unzip python3 python3-pip \
			tesseract tesseract-langpack-rus tesseract-langpack-eng djvulibre
	elif have yum; then
		log "Installing OS packages with yum."
		run_privileged yum install -y \
			ca-certificates curl unzip python3 python3-pip \
			tesseract tesseract-langpack-rus tesseract-langpack-eng djvulibre
	elif have pacman; then
		log "Installing OS packages with pacman."
		run_privileged pacman -S --needed --noconfirm \
			ca-certificates curl unzip python python-pip \
			tesseract tesseract-data-rus tesseract-data-eng djvulibre ||
			die "pacman could not install one or more packages. On Arch, update the system manually with 'sudo pacman -Syu', then rerun this installer."
	elif have zypper; then
		log "Installing OS packages with zypper."
		run_privileged zypper --non-interactive install --no-recommends \
			ca-certificates curl unzip python3 python3-pip \
			tesseract-ocr tesseract-ocr-traineddata-russian \
			tesseract-ocr-traineddata-english djvulibre
	else
		die "Unsupported package manager. Install Python 3.11+, venv, pip, curl, unzip, Tesseract (rus/eng) and DjVuLibre manually."
	fi
}

NEED_OS_PACKAGES=0
have curl || NEED_OS_PACKAGES=1
have unzip || NEED_OS_PACKAGES=1
find_python || NEED_OS_PACKAGES=1
if [ -n "$PYTHON_BIN" ] && ! venv_works; then
	NEED_OS_PACKAGES=1
fi
check_native_tools || NEED_OS_PACKAGES=1

if [ "$NEED_OS_PACKAGES" -eq 1 ]; then
	install_os_packages
fi

have curl || die "curl is still missing after package installation."
have unzip || die "unzip is still missing after package installation."
find_python || die "Python 3.11 or newer is required. Install it with your distribution's supported Python repository, then rerun."
venv_works || die "Python venv/ensurepip is unavailable. Install the matching venv package for Python 3.11+."
check_native_tools || die "Tesseract with rus/eng data and DjVuLibre (djvutxt, djvused, ddjvu) are required. Verify the package names for your distribution."

PYTHON_VERSION=$("$PYTHON_BIN" -c 'import sys; print("{}.{}.{}".format(*sys.version_info[:3]))')
log "Using $PYTHON_BIN (Python $PYTHON_VERSION)."

case "$INSTALL_DIR" in
/*) ;;
*) INSTALL_DIR="$PWD/$INSTALL_DIR" ;;
esac
NEWLINE=$(printf '\nX')
NEWLINE=${NEWLINE%X}
case "$INSTALL_DIR" in
/ | "$HOME" | "$HOME/" | *"$NEWLINE"*) die "Refusing unsafe installation directory: $INSTALL_DIR" ;;
esac
while [ "${INSTALL_DIR%/}" != "$INSTALL_DIR" ]; do
	INSTALL_DIR=${INSTALL_DIR%/}
done
if [ -e "$INSTALL_DIR" ]; then
	die "Installation directory already exists: $INSTALL_DIR. Move it aside or set AUDIODOC_INSTALL_DIR to a new path. Existing data will not be overwritten."
fi

TMP_DIR=$(mktemp -d "${TMPDIR:-/tmp}/audiodoc-install.XXXXXX") ||
	die "Could not create temporary directory."
INSTALL_CREATED=0
INSTALL_SUCCEEDED=0
SYSTEMD_UNIT_CREATED=0

cleanup() {
	if [ -n "${TMP_DIR:-}" ] && [ -d "$TMP_DIR" ]; then
		rm -rf "$TMP_DIR"
	fi
	if [ "${INSTALL_SUCCEEDED:-0}" -ne 1 ]; then
		if [ "${SYSTEMD_UNIT_CREATED:-0}" -eq 1 ]; then
			rm -f "$SYSTEMD_UNIT_FILE"
			systemctl --user daemon-reload >/dev/null 2>&1 || true
		fi
		if [ "${INSTALL_CREATED:-0}" -eq 1 ]; then
			warn "Installation did not complete. Removing incomplete directory: $INSTALL_DIR"
			rm -rf "$INSTALL_DIR"
		fi
	fi
}

trap cleanup 0
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

API_BASE="https://api.github.com/repos/$GITHUB_REPOSITORY"
if [ "$CHANNEL" = "latest" ]; then
	API_URL="$API_BASE/releases/latest"
	log "Looking up the latest stable release."
else
	API_URL="$API_BASE/releases?per_page=100"
	log "Looking up the latest prerelease."
fi
API_JSON="$TMP_DIR/releases.json"
if [ -n "$GITHUB_TOKEN" ]; then
	HTTP_CODE=$(curl -sS -L --retry 3 --retry-delay 2 \
		--connect-timeout 15 --max-time 120 \
		-H 'Accept: application/vnd.github+json' \
		-H 'X-GitHub-Api-Version: 2022-11-28' \
		-H "Authorization: Bearer $GITHUB_TOKEN" \
		-H 'User-Agent: audiodoc-installer' \
		-o "$API_JSON" -w '%{http_code}' "$API_URL") ||
		die "Could not connect to the GitHub Releases API."
else
	HTTP_CODE=$(curl -sS -L --retry 3 --retry-delay 2 \
		--connect-timeout 15 --max-time 120 \
		-H 'Accept: application/vnd.github+json' \
		-H 'X-GitHub-Api-Version: 2022-11-28' \
		-H 'User-Agent: audiodoc-installer' \
		-o "$API_JSON" -w '%{http_code}' "$API_URL") ||
		die "Could not connect to the GitHub Releases API."
fi

if [ "$HTTP_CODE" != "200" ]; then
	if [ "$CHANNEL" = "latest" ] && [ "$HTTP_CODE" = "404" ]; then
		die "No stable release exists yet. Use --nightly for a published prerelease, or wait for the first stable release."
	fi
	if [ "$HTTP_CODE" = "404" ]; then
		die "No matching release was found for $GITHUB_REPOSITORY."
	fi
	die "GitHub Releases API returned HTTP $HTTP_CODE. Check repository access and GITHUB_TOKEN if this is a private repository."
fi

RELEASE_TAG=$("$PYTHON_BIN" - "$CHANNEL" "$API_JSON" <<'PY'
import json
import sys

channel, filename = sys.argv[1:]
with open(filename, encoding="utf-8") as stream:
    payload = json.load(stream)

if channel == "latest":
    release = payload if isinstance(payload, dict) else None
else:
    release = next(
        (item for item in payload if isinstance(item, dict)
         and not item.get("draft") and item.get("prerelease")),
        None,
    ) if isinstance(payload, list) else None

if not release or release.get("draft"):
    raise SystemExit(1)
if channel == "nightly" and not release.get("prerelease"):
    raise SystemExit(1)
print(release.get("tag_name") or "")
PY
) || die "No matching $CHANNEL release was found."
[ -n "$RELEASE_TAG" ] || die "GitHub returned a release with an empty tag name."

RELEASE_ASSETS="$TMP_DIR/release-assets.json"
"$PYTHON_BIN" - "$CHANNEL" "$API_JSON" "$RELEASE_ASSETS" <<'PY'
import json
import sys

channel, source, destination = sys.argv[1:]
with open(source, encoding="utf-8") as stream:
    payload = json.load(stream)
if channel == "latest":
    release = payload
else:
    release = next(item for item in payload
                   if isinstance(item, dict) and not item.get("draft")
                   and item.get("prerelease"))
with open(destination, "w", encoding="utf-8") as stream:
    json.dump(release, stream)
PY

# Prefer the release archive produced by scripts/build_release.sh. Its checksum
# is verified before extraction. GitHub's generated source ZIP remains a fallback.
ASSET_INFO="$TMP_DIR/asset-info.txt"
"$PYTHON_BIN" - "$RELEASE_ASSETS" "$RELEASE_TAG" "$ASSET_INFO" <<'PY'
import json
import sys
from urllib.parse import urlparse

release_file, tag, output = sys.argv[1:]
with open(release_file, encoding="utf-8") as stream:
    release = json.load(stream)
version = tag[1:] if tag.startswith("v") else tag
archive_name = f"audiodoc-{version}.zip"
assets = release.get("assets") or []
archives = [a for a in assets if a.get("name") == archive_name]
sums = [a for a in assets if a.get("name") == "SHA256SUMS"]

if len(archives) > 1 or len(sums) > 1:
    raise SystemExit("Release has duplicate archive or SHA256SUMS assets")
archive_url = None
checksum_url = None
if archives:
    archive_url = archives[0].get("browser_download_url")
    checksum_url = sums[0].get("browser_download_url") if sums else ""
else:
    archive_url = release.get("zipball_url")
    checksum_url = ""

for url in (archive_url, checksum_url):
    if not url:
        continue
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in {"github.com", "api.github.com", "codeload.github.com"}:
        raise SystemExit("GitHub returned an unexpected release asset URL")

with open(output, "w", encoding="utf-8") as stream:
    stream.write((archive_url or "") + "\n")
    stream.write((checksum_url or "") + "\n")
    stream.write((archive_name if archives else "") + "\n")
PY

ARCHIVE_URL=$(sed -n '1p' "$ASSET_INFO")
CHECKSUM_URL=$(sed -n '2p' "$ASSET_INFO")
ARCHIVE_NAME=$(sed -n '3p' "$ASSET_INFO")
[ -n "$ARCHIVE_URL" ] || die "The selected GitHub release has no downloadable archive."

case "$ARCHIVE_URL" in
https://github.com/* | https://api.github.com/* | https://codeload.github.com/*) ;;
*) die "GitHub returned an unexpected archive URL. Refusing to download." ;;
esac

ZIP_FILE="$TMP_DIR/release.zip"
log "Selected release: $RELEASE_TAG."
if [ -n "$ARCHIVE_NAME" ]; then
	log "Downloading the project's release archive."
else
	warn "This release has no audiodoc release asset; using GitHub's generated source ZIP without a published SHA256SUMS."
fi
curl -fLsS --retry 3 --retry-delay 2 --connect-timeout 15 \
	-H 'User-Agent: audiodoc-installer' -o "$ZIP_FILE" "$ARCHIVE_URL" ||
	die "Could not download the release ZIP."

if [ -n "$ARCHIVE_NAME" ] && [ -n "$CHECKSUM_URL" ]; then
	CHECKSUM_FILE="$TMP_DIR/SHA256SUMS"
	curl -fLsS --retry 3 --retry-delay 2 --connect-timeout 15 \
		-H 'User-Agent: audiodoc-installer' -o "$CHECKSUM_FILE" "$CHECKSUM_URL" ||
		die "The release archive exists but SHA256SUMS could not be downloaded. Refusing to continue."
	"$PYTHON_BIN" - "$ZIP_FILE" "$CHECKSUM_FILE" "$ARCHIVE_NAME" <<'PY'
import hashlib
import re
import sys
from pathlib import Path

archive = Path(sys.argv[1])
checksums = Path(sys.argv[2])
expected_name = sys.argv[3]
matches = []
for line in checksums.read_text(encoding="utf-8").splitlines():
    match = re.fullmatch(r"([0-9a-fA-F]{64})  (.+)", line)
    if match and match.group(2) == expected_name:
        matches.append(match.group(1).lower())
if len(matches) != 1:
    raise SystemExit("SHA256SUMS must contain exactly one entry for the release ZIP")
hasher = hashlib.sha256()
with archive.open("rb") as stream:
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        hasher.update(chunk)
digest = hasher.hexdigest()
if digest != matches[0]:
    raise SystemExit("Release archive SHA-256 mismatch")
print("Verified SHA-256 for " + expected_name)
PY
elif [ -n "$ARCHIVE_NAME" ]; then
	warn "The release asset has no SHA256SUMS file. Downloaded over HTTPS, but integrity could not be independently verified."
fi

# Reject traversal, absolute paths, symlinks, and unusually large archives before unzip.
"$PYTHON_BIN" - "$ZIP_FILE" <<'PY'
import stat
import sys
from pathlib import PurePosixPath
from zipfile import BadZipFile, ZipFile

max_uncompressed = 2 * 1024 * 1024 * 1024
try:
    with ZipFile(sys.argv[1]) as archive:
        total_size = 0
        if not archive.infolist():
            raise SystemExit("Release ZIP is empty")
        for item in archive.infolist():
            name = item.filename
            path = PurePosixPath(name)
            mode = item.external_attr >> 16
            total_size += item.file_size
            if path.is_absolute() or ".." in path.parts or "\\" in name:
                raise SystemExit("Unsafe path in release archive: " + name)
            if stat.S_ISLNK(mode):
                raise SystemExit("Symlinks are not allowed in the release archive: " + name)
            if total_size > max_uncompressed:
                raise SystemExit("Release ZIP expands beyond the 2 GiB safety limit")
except BadZipFile:
    raise SystemExit("Downloaded file is not a valid ZIP archive")
PY

EXTRACT_DIR="$TMP_DIR/extracted"
mkdir -p "$EXTRACT_DIR"
unzip -q "$ZIP_FILE" -d "$EXTRACT_DIR" || die "Could not extract release ZIP."
SOURCE_DIR=$("$PYTHON_BIN" - "$EXTRACT_DIR" <<'PY'
import sys
from pathlib import Path

base = Path(sys.argv[1])
matches = set()
for app_file in base.rglob("app.py"):
    root = app_file.parent
    if ((root / "backend" / "main.py").is_file()
            and (root / ".env.example").is_file()
            and (root / "requirements-lock.txt").is_file()):
        matches.add(root)
if len(matches) != 1:
    raise SystemExit(
        "Expected exactly one audiodoc project root containing app.py, backend/main.py, "
        ".env.example and requirements-lock.txt; found {}".format(len(matches))
    )
print(next(iter(matches)))
PY
) || die "Release ZIP does not contain the expected audiodoc project layout."

log "Installing release into $INSTALL_DIR."
mkdir -p "$INSTALL_DIR"
INSTALL_CREATED=1
cp -R "$SOURCE_DIR/." "$INSTALL_DIR/"
[ -f "$INSTALL_DIR/.env.example" ] || die "Release archive is missing .env.example."
mv "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"
chmod 600 "$INSTALL_DIR/.env"

log "Creating Python virtual environment."
"$PYTHON_BIN" -m venv "$INSTALL_DIR/.venv"
"$INSTALL_DIR/.venv/bin/python" -m pip install \
	--disable-pip-version-check \
	-r "$INSTALL_DIR/requirements-lock.txt"

mkdir -p "$INSTALL_DIR/tmp"
chmod 700 "$INSTALL_DIR/tmp"

MODEL_PATH=""
if [ "$DOWNLOAD_MODEL" -eq 1 ]; then
	log "Whisper model '$MODEL' will be downloaded. This requires internet access and several hundred MB (large models require substantially more)."
	if [ "$ASSUME_YES" -ne 1 ]; then
		printf 'Download the Whisper model now? [Y/n] ' >/dev/tty 2>/dev/null ||
			die "No interactive terminal is available. Use --yes to confirm model download, or --no-model to skip it."
		IFS= read -r reply </dev/tty || reply=""
		case "$reply" in
		n | N | no | NO) die "Model download declined. Rerun with --no-model to skip model provisioning." ;;
		*) ;;
		esac
	fi
	MODEL_OUTPUT_DIR="$INSTALL_DIR/models/$MODEL"
	mkdir -p "$MODEL_OUTPUT_DIR"
	MODEL_PATH=$(cd "$INSTALL_DIR" && "$INSTALL_DIR/.venv/bin/python" - "$MODEL" "$MODEL_OUTPUT_DIR" <<'PY'
import sys
from pathlib import Path
from faster_whisper.utils import download_model

model_name, output_dir = sys.argv[1:]
result = download_model(model_name, output_dir=output_dir)
path = Path(result).resolve()
if not path.is_dir():
    raise SystemExit("faster-whisper did not produce a model directory")
print(path)
PY
) || die "Whisper model download failed. Check network access, available disk space, and model name."
	[ -n "$MODEL_PATH" ] || die "Whisper model download returned an empty path."
fi

# Generate distinct access keys and write .env plus the bot snippet without
# exposing either key in terminal output or shell command arguments.
BOT_SNIPPET="$INSTALL_DIR/bot-env-snippet.txt"
"$PYTHON_BIN" - "$INSTALL_DIR/.env" "$BOT_SNIPPET" "$MODEL" "$MODEL_PATH" "$DEVICE" "$COMPUTE_TYPE" "$HOST" "$PORT" <<'PY'
import secrets
import sys
from pathlib import Path

(env_path, snippet_path, model, model_path, device, compute_type,
 host, port) = sys.argv[1:]
env_file = Path(env_path)
lines = env_file.read_text(encoding="utf-8").splitlines()
key_whisper = secrets.token_urlsafe(32)
key_document = secrets.token_urlsafe(32)
while key_document == key_whisper:
    key_document = secrets.token_urlsafe(32)
updates = {
    "WHISPER_API_KEY": key_whisper,
    "DOCUMENT_API_KEY": key_document,
    "WHISPER_MODEL_SIZE": model,
    "WHISPER_MODEL_PATH": model_path,
    "WHISPER_DEVICE": device,
    "WHISPER_COMPUTE_TYPE": compute_type,
    "WHISPER_OFFLINE": "true" if model_path else "false",
}
counts = {name: 0 for name in updates}
rewritten = []
for line in lines:
    stripped = line.lstrip()
    replaced = False
    for name, value in updates.items():
        if stripped.startswith(name + "="):
            counts[name] += 1
            if name == "WHISPER_MODEL_PATH" and value:
                escaped = value.replace("\\", "\\\\").replace('"', '\\"')
                rewritten.append(f'{name}="{escaped}"')
            else:
                rewritten.append(f"{name}={value}")
            replaced = True
            break
    if not replaced:
        rewritten.append(line)
missing = [name for name, count in counts.items() if count != 1]
if missing:
    raise SystemExit(".env.example must contain each setting exactly once: " + ", ".join(missing))
env_file.write_text("\n".join(rewritten) + "\n", encoding="utf-8")
env_file.chmod(0o600)

if host in {"127.0.0.1", "localhost"}:
    connect_host = host
    note = "# This address works only when the bot runs on this same machine. For a remote bot, replace the host with this server's private/VPN address."
elif host in {"0.0.0.0", "::"}:
    connect_host = "SERVER_PRIVATE_IP"
    note = "# Replace SERVER_PRIVATE_IP with the server's private/VPN address. Do not use 0.0.0.0 as a client destination."
else:
    connect_host = f"[{host}]" if ":" in host else host
    note = "# Confirm this address is reachable from the bot machine and restricted by the host firewall."
base_url = f"http://{connect_host}:{port}"
content = (
    "# Copy these values into bot-obormot/.env. Keep the two keys separate.\n"
    + note + "\n"
    + f"WHISPER_API_URL={base_url}/transcribe\n"
    + f"WHISPER_API_KEY={key_whisper}\n"
    + f"DOCUMENT_API_URL={base_url}/process-document\n"
    + f"DOCUMENT_API_KEY={key_document}\n"
)
snippet = Path(snippet_path)
snippet.write_text(content, encoding="utf-8")
snippet.chmod(0o600)
PY

log "Checking that the application and installed dependencies import successfully."
(
	cd "$INSTALL_DIR"
	"$INSTALL_DIR/.venv/bin/python" -c 'import backend.main'
) || die "Application import check failed. Review the Python dependency installation and release contents."

if [ "$CREATE_SYSTEMD" -eq 1 ]; then
	mkdir -p "$SYSTEMD_USER_DIR"
	SYSTEMD_WORKDIR=$(printf '%s' "$INSTALL_DIR" | sed 's/\\/\\\\/g; s/"/\\"/g; s/%/%%/g')
	SYSTEMD_ENVFILE=$(printf '%s' "$INSTALL_DIR/.env" | sed 's/\\/\\\\/g; s/"/\\"/g; s/%/%%/g')
	SYSTEMD_EXEC=$(printf '%s' "$INSTALL_DIR/.venv/bin/uvicorn" | sed 's/\\/\\\\/g; s/"/\\"/g; s/%/%%/g')
	SYSTEMD_UNIT_CREATED=1
	cat >"$SYSTEMD_UNIT_FILE" <<EOF
[Unit]
Description=audiodoc FastAPI service
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
WorkingDirectory="$SYSTEMD_WORKDIR"
EnvironmentFile="$SYSTEMD_ENVFILE"
Environment=PYTHONUNBUFFERED=1
ExecStart="$SYSTEMD_EXEC" app:app --host $HOST --port $PORT --no-server-header
Restart=on-failure
RestartSec=5
UMask=0077

[Install]
WantedBy=default.target
EOF
	chmod 600 "$SYSTEMD_UNIT_FILE"
	systemctl --user daemon-reload || die "Could not reload the user systemd manager."
	log "Created user systemd unit: $SYSTEMD_UNIT_FILE"
fi

INSTALL_SUCCEEDED=1
cat <<EOF

Installation completed successfully.

Project directory:
  $INSTALL_DIR

Protected configuration:
  $INSTALL_DIR/.env

Bot configuration snippet (contains secrets; permissions are 600):
  $BOT_SNIPPET
  Display it locally with: cat "$BOT_SNIPPET"

Next steps:
  1. Review $INSTALL_DIR/.env and keep ALLOW_UNAUTHENTICATED=false.
  2. Copy the values from bot-env-snippet.txt into bot-obormot/.env.
  3. From the bot machine, verify /health, authenticated /ready, document processing and transcription.
  4. Restrict TCP $PORT to the bot's private/VPN address, or use the reviewed HTTPS/nginx configuration.
EOF

if [ "$DOWNLOAD_MODEL" -eq 0 ]; then
	cat <<EOF

No Whisper model was downloaded (--no-model).
The first service startup may download '$MODEL' from the model hub. For offline operation, place the model under $INSTALL_DIR/models and set WHISPER_MODEL_PATH plus WHISPER_OFFLINE=true in .env.
EOF
fi

if [ "$DEVICE" = "cuda" ]; then
	warn "CUDA was selected. Confirm that NVIDIA drivers and a CUDA-compatible CTranslate2 runtime are installed and accessible to this user. This installer does not install GPU drivers."
fi

if [ "$CREATE_SYSTEMD" -eq 1 ]; then
	cat <<EOF

A per-user systemd unit was created and systemd reloaded.
The unit was NOT enabled or started. Review .env first, then run:

  systemctl --user enable --now audiodoc.service
  systemctl --user status audiodoc.service
  journalctl --user -u audiodoc.service -f

For startup without an interactive login, an administrator may enable lingering:
  sudo loginctl enable-linger "$RUNNING_USER"
EOF
else
	cat <<EOF

Run manually:
  cd "$INSTALL_DIR"
  .venv/bin/uvicorn app:app --host "$HOST" --port "$PORT" --no-server-header
EOF
fi

log "Installed release $RELEASE_TAG ($CHANNEL)."
