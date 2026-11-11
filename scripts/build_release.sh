#!/usr/bin/env bash
set -euo pipefail

VERSION="${1:?usage: build_release.sh VERSION}"

if [[ ! "$VERSION" =~ ^[0-9A-Za-z][0-9A-Za-z.+-]*$ ]]; then
  echo "Invalid release version: $VERSION" >&2
  exit 2
fi

PROJECT_VERSION="$(python3 -c 'import tomllib; from pathlib import Path; print(tomllib.loads(Path("pyproject.toml").read_text())["project"]["version"])')"
if [[ "$VERSION" != "$PROJECT_VERSION" ]]; then
  echo "Release version ${VERSION} does not match pyproject.toml version ${PROJECT_VERSION}." >&2
  exit 2
fi

mkdir -p dist
rm -f dist/audiodoc-*.whl dist/constraints.txt dist/SHA256SUMS

python3 -m pip wheel \
  --disable-pip-version-check \
  --no-deps \
  --wheel-dir dist \
  .

shopt -s nullglob
wheels=(dist/audiodoc-*.whl)
if [[ ${#wheels[@]} -ne 1 ]]; then
  echo "Expected exactly one audiodoc wheel in dist/, found ${#wheels[@]}." >&2
  exit 1
fi

cp requirements-lock.txt dist/constraints.txt

(
  cd dist
  sha256sum "${wheels[0]##*/}" constraints.txt > SHA256SUMS
)

printf 'Built dist/%s, dist/constraints.txt and dist/SHA256SUMS\n' \
  "${wheels[0]##*/}"
