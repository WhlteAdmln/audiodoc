#!/bin/sh
# audiodoc installer. Installs a verified GitHub Release wheel.

set -eu
umask 077

APP_NAME="audiodoc"
GITHUB_REPOSITORY="${AUDIODOC_GITHUB_REPOSITORY:-WhlteAdmln/audiodoc}"
MODEL="small"
DEVICE="cpu"
COMPUTE_TYPE=""
HOST="127.0.0.1"
PORT="8000"
NO_MODEL=0
CREATE_SYSTEMD=0
INSTALL_OS_PACKAGES=0
PYTHON_BIN=""
UPGRADE=0
INSTALL_OPTIONS=0
UPGRADE_BACKUP=0
INSTALL_CREATED=0
INSTALL_SUCCEEDED=0

log() {
	printf '%s\n' "[$APP_NAME] $*"
}

die() {
	printf '%s\n' "[$APP_NAME] ERROR: $*" >&2
	exit 1
}

usage() {
	cat <<'EOF'
Usage: install.sh [options]

  --model NAME         Whisper model (default: small).
  --device cpu|cuda    Inference device (default: cpu).
  --compute-type TYPE  CTranslate2 compute type.
  --host ADDR          Server bind address (default: 127.0.0.1).
  --port N             Server port (default: 8000).
  --no-model           Skip downloading the Whisper model.
  --systemd            Install a per-user systemd unit.
  --os-packages        Run native package commands printed by doctor.
  --upgrade            Safely upgrade an existing installation.
  --help               Show this help.

Environment:
  AUDIODOC_HOME               Installation directory (default: ~/audiodoc).
  AUDIODOC_RELEASE_URL        Release asset base URL (used for local mirrors).
  AUDIODOC_RELEASE_TAG        Release tag for a custom release URL.
  AUDIODOC_GITHUB_REPOSITORY  GitHub repository (default: WhlteAdmln/audiodoc).
  GITHUB_TOKEN                Optional GitHub API token.

Requires Linux with glibc, Python 3.11+, venv, curl and sha256sum.
Alpine Linux is not supported because release wheels require glibc.
EOF
}

need_value() {
	[ "$#" -ge 2 ] || die "Option $1 requires a value."
	case "$2" in
	'' | -*)
		die "Invalid value for $1: $2"
		;;
	esac
}

while [ "$#" -gt 0 ]; do
	case "$1" in
	--model)
		need_value "$@"
		MODEL=$2
		INSTALL_OPTIONS=$((INSTALL_OPTIONS + 1))
		shift
		;;
	--device)
		need_value "$@"
		DEVICE=$2
		INSTALL_OPTIONS=$((INSTALL_OPTIONS + 1))
		shift
		;;
	--compute-type)
		need_value "$@"
		COMPUTE_TYPE=$2
		INSTALL_OPTIONS=$((INSTALL_OPTIONS + 1))
		shift
		;;
	--host)
		need_value "$@"
		HOST=$2
		INSTALL_OPTIONS=$((INSTALL_OPTIONS + 1))
		shift
		;;
	--port)
		need_value "$@"
		PORT=$2
		INSTALL_OPTIONS=$((INSTALL_OPTIONS + 1))
		shift
		;;
	--no-model)
		NO_MODEL=1
		INSTALL_OPTIONS=$((INSTALL_OPTIONS + 1))
		;;
	--systemd)
		CREATE_SYSTEMD=1
		INSTALL_OPTIONS=$((INSTALL_OPTIONS + 1))
		;;
	--os-packages)
		INSTALL_OS_PACKAGES=1
		INSTALL_OPTIONS=$((INSTALL_OPTIONS + 1))
		;;
	--upgrade)
		UPGRADE=1
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

if [ "$UPGRADE" -eq 1 ] && [ "$INSTALL_OPTIONS" -ne 0 ]; then
	die "--upgrade cannot be combined with installation configuration options."
fi

case "$GITHUB_REPOSITORY" in
*/*)
	case "$GITHUB_REPOSITORY" in
	*[!A-Za-z0-9._/-]* | */*/* | /* | */)
		die "Invalid GitHub repository: $GITHUB_REPOSITORY"
		;;
	esac
	;;
*)
	die "AUDIODOC_GITHUB_REPOSITORY must have owner/name format."
	;;
esac

case "$MODEL" in
tiny | tiny.en | base | base.en | small | small.en | medium | medium.en | \
	large | large-v1 | large-v2 | large-v3 | large-v3-turbo | turbo | \
	distil-small.en | distil-medium.en | distil-large-v2 | distil-large-v3)
	;;
*)
	die "Unsupported Whisper model name: $MODEL"
	;;
esac

case "$DEVICE" in
cpu | cuda)
	;;
*)
	die "--device must be cpu or cuda."
	;;
esac

if [ -z "$COMPUTE_TYPE" ]; then
	if [ "$DEVICE" = "cuda" ]; then
		COMPUTE_TYPE="float16"
	else
		COMPUTE_TYPE="int8"
	fi
fi

case "$COMPUTE_TYPE" in
'' | *[!A-Za-z0-9_-]*)
	die "Invalid compute type: $COMPUTE_TYPE"
	;;
esac

case "$HOST" in
'' | -* | *[!A-Za-z0-9.:-]*)
	die "Invalid host address: $HOST"
	;;
esac

case "$PORT" in
'' | *[!0-9]*)
	die "Port must be an integer between 1 and 65535."
	;;
esac

awk -v port="$PORT" 'BEGIN { exit !(port >= 1 && port <= 65535 && int(port) == port) }' ||
	die "Port must be an integer between 1 and 65535."

[ -n "${HOME:-}" ] && [ -d "$HOME" ] ||
	die "HOME must point to an existing directory."

if command -v apk >/dev/null 2>&1; then
	die "Alpine Linux is not supported: audiodoc release wheels require glibc."
fi

if [ -n "${AUDIODOC_HOME:-}" ]; then
	HOME_DIR=$AUDIODOC_HOME
else
	HOME_DIR=$HOME/audiodoc
fi

case "$HOME_DIR" in
/*)
	;;
*)
	HOME_DIR=$PWD/$HOME_DIR
	;;
esac

while [ "$HOME_DIR" != "/" ] && [ "${HOME_DIR%/}" != "$HOME_DIR" ]; do
	HOME_DIR=${HOME_DIR%/}
done

case "$HOME_DIR" in
/ | "$HOME")
	die "Refusing unsafe installation directory: $HOME_DIR"
	;;
esac

refuse_active_service() {
	if command -v systemctl >/dev/null 2>&1 &&
		systemctl --user is-active --quiet audiodoc.service; then
		die "The audiodoc user service is active. Stop it manually before upgrading."
	fi
}

if [ "$UPGRADE" -eq 1 ]; then
	[ -d "$HOME_DIR" ] && [ ! -L "$HOME_DIR" ] ||
		die "Upgrade requires an existing installation directory: $HOME_DIR"
	[ -f "$HOME_DIR/.env" ] && [ ! -L "$HOME_DIR/.env" ] ||
		die "Upgrade requires an existing regular .env file."
	[ -d "$HOME_DIR/.venv" ] && [ ! -L "$HOME_DIR/.venv" ] ||
		die "Upgrade requires an existing .venv directory."
	[ -x "$HOME_DIR/.venv/bin/python" ] ||
		die "The existing virtual environment has no executable Python interpreter."
	[ ! -e "$HOME_DIR/.venv.new" ] && [ ! -L "$HOME_DIR/.venv.new" ] ||
		die "Refusing to overwrite stale upgrade directory: $HOME_DIR/.venv.new"
	[ ! -e "$HOME_DIR/.venv.prev" ] && [ ! -L "$HOME_DIR/.venv.prev" ] ||
		die "Refusing to overwrite stale upgrade backup: $HOME_DIR/.venv.prev"

	if [ -f "$HOME_DIR/backend/main.py" ] &&
		! "$HOME_DIR/.venv/bin/python" -c \
			'import sysconfig
from pathlib import Path
paths = sysconfig.get_paths()
raise SystemExit(
    0
    if any(
        (Path(paths[key]) / "audiodoc").is_dir()
        for key in ("purelib", "platlib")
    )
    else 1
)' \
			>/dev/null 2>&1; then
		die "Legacy audiodoc 0.1.0 installation detected. Follow the migration procedure in task A-4.10 before upgrading."
	fi

	refuse_active_service
else
	if [ -e "$HOME_DIR" ] || [ -L "$HOME_DIR" ]; then
		die "Installation directory already exists: $HOME_DIR. Use --upgrade to update an existing installation."
	fi
fi

command -v curl >/dev/null 2>&1 || die "curl is required."
command -v sha256sum >/dev/null 2>&1 || die "sha256sum is required."

find_python() {
	for candidate in python3.14 python3.13 python3.12 python3.11 python3; do
		if command -v "$candidate" >/dev/null 2>&1; then
			candidate_path=$(command -v "$candidate")
			if "$candidate_path" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1; then
				PYTHON_BIN=$candidate_path
				return 0
			fi
		fi
	done
	return 1
}

find_python || die "Python 3.11 or newer is required."

TMP_DIR=$(mktemp -d "${TMPDIR:-/tmp}/audiodoc-install.XXXXXX") ||
	die "Could not create a temporary directory."

cleanup() {
	result=$?
	trap - 0
	rm -rf "$TMP_DIR"
	if [ "$UPGRADE" -eq 1 ]; then
		rm -rf "$HOME_DIR/.venv.new"
		if [ "$UPGRADE_BACKUP" -eq 1 ] &&
			[ ! -e "$HOME_DIR/.venv" ] &&
			[ -e "$HOME_DIR/.venv.prev" ]; then
			mv "$HOME_DIR/.venv.prev" "$HOME_DIR/.venv" ||
				printf '%s\n' "[$APP_NAME] ERROR: Could not restore the previous virtual environment." >&2
		fi
	fi
	if [ "$INSTALL_CREATED" -eq 1 ] && [ "$INSTALL_SUCCEEDED" -ne 1 ]; then
		rm -rf "$HOME_DIR"
	fi
	exit "$result"
}

trap cleanup 0
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

"$PYTHON_BIN" -m venv "$TMP_DIR/venv-probe" >/dev/null 2>&1 ||
	die "Python venv is unavailable. Install the venv package for Python 3.11+."

"$TMP_DIR/venv-probe/bin/python" -m pip --version >/dev/null 2>&1 ||
	die "Python venv does not provide pip. Install the matching venv package."

rm -rf "$TMP_DIR/venv-probe"

RELEASE_TAG=${AUDIODOC_RELEASE_TAG:-local}

if [ -n "${AUDIODOC_RELEASE_URL:-}" ]; then
	RELEASE_URL=${AUDIODOC_RELEASE_URL%/}
else
	API_URL="https://api.github.com/repos/$GITHUB_REPOSITORY/releases/latest"
	API_JSON="$TMP_DIR/release.json"
	log "Looking up the latest stable release."

	if [ -n "${GITHUB_TOKEN:-}" ]; then
		curl -fLsS --retry 3 --connect-timeout 15 \
			-H 'Accept: application/vnd.github+json' \
			-H "Authorization: Bearer $GITHUB_TOKEN" \
			-o "$API_JSON" "$API_URL" ||
			die "Could not retrieve the latest GitHub release."
	else
		curl -fLsS --retry 3 --connect-timeout 15 \
			-H 'Accept: application/vnd.github+json' \
			-o "$API_JSON" \
			"$API_URL" ||
			die "Could not retrieve the latest GitHub release."
	fi

	RELEASE_INFO="$TMP_DIR/release-info.txt"
	"$PYTHON_BIN" - "$API_JSON" "$RELEASE_INFO" <<'PY' ||
		die "GitHub returned invalid release metadata."
import json
import re
import sys

source, destination = sys.argv[1:]
with open(source, encoding="utf-8") as stream:
    release = json.load(stream)

if not isinstance(release, dict) or release.get("draft"):
    raise SystemExit("Invalid release metadata")

tag = release.get("tag_name")
if not isinstance(tag, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+-]*", tag):
    raise SystemExit("Invalid release tag")

assets = release.get("assets") or []
wheels = [
    item for item in assets
    if isinstance(item, dict)
    and isinstance(item.get("name"), str)
    and item["name"].startswith("audiodoc-")
    and item["name"].endswith(".whl")
]

with open(destination, "w", encoding="utf-8") as stream:
    stream.write(tag + "\n")
    stream.write(str(len(wheels)) + "\n")
PY
		RELEASE_TAG=$(sed -n '1p' "$RELEASE_INFO")
	WHEEL_ASSET_COUNT=$(sed -n '2p' "$RELEASE_INFO")

	if [ "$WHEEL_ASSET_COUNT" -eq 0 ]; then
		die "Release $RELEASE_TAG has no wheel asset. Use the installer at https://raw.githubusercontent.com/$GITHUB_REPOSITORY/$RELEASE_TAG/install.sh"
	fi

	if [ "$WHEEL_ASSET_COUNT" -ne 1 ]; then
		die "Release $RELEASE_TAG contains multiple audiodoc wheels."
	fi

	RELEASE_URL="https://github.com/$GITHUB_REPOSITORY/releases/download/$RELEASE_TAG"
fi

case "$RELEASE_TAG" in
'' | *[!A-Za-z0-9._+-]*)
	die "Invalid release tag: $RELEASE_TAG"
	;;
esac

download_asset() {
	asset_name=$1
	curl -fLsS --retry 3 --connect-timeout 15 --max-time 120 \
		-o "$TMP_DIR/$asset_name" "$RELEASE_URL/$asset_name" ||
		die "Could not download release asset: $asset_name"
}

log "Selected release: $RELEASE_TAG."
download_asset SHA256SUMS

VERIFY_SUMS="$TMP_DIR/verified-SHA256SUMS"
WHEEL_NAME=$(
	"$PYTHON_BIN" - "$TMP_DIR/SHA256SUMS" "$VERIFY_SUMS" <<'PY'
import re
import sys
from pathlib import Path

source, destination = map(Path, sys.argv[1:])
entries = {}
for line in source.read_text(encoding="utf-8").splitlines():
    match = re.fullmatch(r"([0-9a-fA-F]{64})  ([A-Za-z0-9_.+-]+)", line)
    if match:
        digest, name = match.groups()
        if name in entries:
            raise SystemExit("Duplicate SHA256SUMS entry: " + name)
        entries[name] = digest

wheels = [
    name for name in entries
    if name.startswith("audiodoc-") and name.endswith(".whl")
]
if not wheels:
    print("__NO_WHEEL__")
    raise SystemExit(0)
if len(wheels) != 1:
    raise SystemExit("SHA256SUMS must contain exactly one audiodoc wheel")
if "constraints.txt" not in entries:
    raise SystemExit("SHA256SUMS does not contain constraints.txt")

wheel = wheels[0]
lines = [
    f"{entries[wheel]}  {wheel}",
    f"{entries['constraints.txt']}  constraints.txt",
]
destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(wheel)
PY
) || die "Release SHA256SUMS is invalid."

if [ "$WHEEL_NAME" = "__NO_WHEEL__" ]; then
	die "Release $RELEASE_TAG has no wheel asset. Use the installer at https://raw.githubusercontent.com/$GITHUB_REPOSITORY/$RELEASE_TAG/install.sh"
fi

download_asset "$WHEEL_NAME"
download_asset constraints.txt

(cd "$TMP_DIR" && sha256sum -c "$VERIFY_SUMS") ||
	die "Release SHA-256 verification failed."

if [ "$UPGRADE" -eq 1 ]; then
	NEW_VENV="$HOME_DIR/.venv.new"
	NEW_PYTHON="$NEW_VENV/bin/python"
	NEW_CLI="$NEW_VENV/bin/audiodoc"

	log "Creating a staged virtual environment."
	"$PYTHON_BIN" -m venv "$NEW_VENV" ||
		die "Could not create the staged virtual environment."

	log "Installing the verified release wheel into the staged environment."
	"$NEW_PYTHON" -m pip install \
		--disable-pip-version-check \
		--constraint "$TMP_DIR/constraints.txt" \
		"$TMP_DIR/$WHEEL_NAME" ||
		die "Could not install the audiodoc release wheel into the staged environment."

	log "Checking the staged installation in offline mode."
	DOCTOR_OUTPUT="$TMP_DIR/doctor-upgrade.txt"
	if AUDIODOC_HOME="$HOME_DIR" "$NEW_CLI" doctor --offline \
		>"$DOCTOR_OUTPUT" 2>&1; then
		cat "$DOCTOR_OUTPUT"
	else
		cat "$DOCTOR_OUTPUT"
		die "Staged audiodoc doctor --offline failed. The existing installation was not replaced."
	fi

	refuse_active_service

	log "Switching the application virtual environment."
	mv "$HOME_DIR/.venv" "$HOME_DIR/.venv.prev" ||
		die "Could not move the existing virtual environment to its backup."
	UPGRADE_BACKUP=1

	mv "$NEW_VENV" "$HOME_DIR/.venv" ||
		die "Could not activate the staged virtual environment. The previous environment will be restored."

	if rm -rf "$HOME_DIR/.venv.prev"; then
		UPGRADE_BACKUP=0
	else
		log "WARNING: Could not remove the previous environment backup: $HOME_DIR/.venv.prev"
		UPGRADE_BACKUP=0
	fi

	INSTALL_SUCCEEDED=1
	cat <<EOF

Upgrade completed successfully.

Application directory:
  $HOME_DIR

Virtual environment:
  $HOME_DIR/.venv

The installer preserved .env, models/, tmp/, and the existing systemd unit.
The installer did not restart or enable the systemd service.

If the audiodoc user service is installed, restart it manually when ready:
  systemctl --user restart audiodoc.service
EOF

	log "Upgraded to release $RELEASE_TAG."
	exit 0
fi

log "Creating installation directory: $HOME_DIR"
mkdir -p "${HOME_DIR%/*}"
mkdir "$HOME_DIR" || die "Could not create installation directory: $HOME_DIR"
INSTALL_CREATED=1

log "Creating Python virtual environment."
"$PYTHON_BIN" -m venv "$HOME_DIR/.venv" ||
	die "Could not create the application virtual environment."

VENV_PYTHON="$HOME_DIR/.venv/bin/python"
APP_CLI="$HOME_DIR/.venv/bin/audiodoc"

log "Installing the verified release wheel."
"$VENV_PYTHON" -m pip install \
	--disable-pip-version-check \
	--constraint "$TMP_DIR/constraints.txt" \
	"$TMP_DIR/$WHEEL_NAME" ||
	die "Could not install the audiodoc release wheel."

log "Initializing protected application configuration."
AUDIODOC_HOME="$HOME_DIR" "$APP_CLI" init \
	--model "$MODEL" \
	--device "$DEVICE" \
	--compute-type "$COMPUTE_TYPE" \
	--host "$HOST" \
	--port "$PORT" ||
	die "audiodoc init failed."

if [ "$NO_MODEL" -eq 0 ]; then
	MODEL_PATH="$HOME_DIR/models/$MODEL"
	log "Downloading Whisper model: $MODEL."
	AUDIODOC_HOME="$HOME_DIR" "$APP_CLI" model download \
		--name "$MODEL" \
		--dir "$MODEL_PATH" ||
		die "Whisper model download failed."

	if ! "$VENV_PYTHON" - "$HOME_DIR/.env" "$MODEL_PATH" <<'PY'; then
import sys
from pathlib import Path

env_path = Path(sys.argv[1])
model_path = sys.argv[2]
updates = {
    "WHISPER_MODEL_PATH": model_path,
    "WHISPER_OFFLINE": "true",
}
counts = {name: 0 for name in updates}
rewritten = []

for line in env_path.read_text(encoding="utf-8").splitlines():
    key, separator, _value = line.partition("=")
    if separator and key in updates:
        value = updates[key]
        if key == "WHISPER_MODEL_PATH":
            value = '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
        rewritten.append(f"{key}={value}")
        counts[key] += 1
    else:
        rewritten.append(line)

if any(count != 1 for count in counts.values()):
    raise SystemExit("Unexpected .env model settings")

env_path.write_text("\n".join(rewritten) + "\n", encoding="utf-8")
env_path.chmod(0o600)
PY
		die "Could not update the model configuration."
	fi
else
	log "Skipping Whisper model download (--no-model)."
fi

DOCTOR_OUTPUT="$TMP_DIR/doctor.txt"
if AUDIODOC_HOME="$HOME_DIR" "$APP_CLI" doctor >"$DOCTOR_OUTPUT" 2>&1; then
	cat "$DOCTOR_OUTPUT"
else
	cat "$DOCTOR_OUTPUT"

	if [ "$INSTALL_OS_PACKAGES" -ne 1 ]; then
		die "audiodoc doctor failed. Review the diagnostics above. Use --os-packages to run the recommended native package command."
	fi

	if command -v apt-get >/dev/null 2>&1; then
		DOCTOR_PREFIX="  Debian/Ubuntu: "
	elif command -v dnf >/dev/null 2>&1; then
		DOCTOR_PREFIX="  Fedora/RHEL: "
	elif command -v pacman >/dev/null 2>&1; then
		DOCTOR_PREFIX="  Arch Linux: "
	else
		die "Unsupported package manager. Only apt, dnf and pacman are supported by --os-packages."
	fi

	PACKAGE_COMMAND=$(
		awk -v prefix="$DOCTOR_PREFIX" \
			'index($0, prefix) == 1 { print substr($0, length(prefix) + 1); exit }' \
			"$DOCTOR_OUTPUT"
	)
	[ -n "$PACKAGE_COMMAND" ] ||
		die "audiodoc doctor did not provide a package command for this distribution."

	log "Running the native package command printed by doctor."
	sh -c "$PACKAGE_COMMAND" ||
		die "The native package installation command failed."

	if ! AUDIODOC_HOME="$HOME_DIR" "$APP_CLI" doctor >"$DOCTOR_OUTPUT" 2>&1; then
		cat "$DOCTOR_OUTPUT"
		die "audiodoc doctor still reports errors after OS package installation."
	fi
	cat "$DOCTOR_OUTPUT"
fi

if [ "$CREATE_SYSTEMD" -eq 1 ]; then
	log "Installing the per-user systemd unit."
	(
		cd "$HOME_DIR"
		AUDIODOC_HOME="$HOME_DIR" "$VENV_PYTHON" -m audiodoc service install --user
	) ||
		die "Could not install the user systemd unit."
fi

INSTALL_SUCCEEDED=1

cat <<EOF

Installation completed successfully.

Application directory:
  $HOME_DIR

Protected configuration:
  $HOME_DIR/.env

Virtual environment:
  $HOME_DIR/.venv

Run manually:
  AUDIODOC_HOME="$HOME_DIR" "$APP_CLI" run --host "$HOST" --port "$PORT"

The installer does not enable or start the systemd service.
Review .env and enable the service manually when ready.
EOF

log "Installed release $RELEASE_TAG."
