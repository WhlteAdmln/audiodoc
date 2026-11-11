#!/usr/bin/env bash
set -euo pipefail

VERSION="${1:?usage: build_release.sh VERSION}"

if [[ ! "$VERSION" =~ ^[0-9A-Za-z][0-9A-Za-z.+-]*$ ]]; then
  echo "Invalid release version: $VERSION" >&2
  exit 2
fi

mkdir -p dist
rm -f dist/audiodoc-*.zip dist/audiodoc-*.tar.gz dist/audiodoc-*.whl \
  dist/constraints.txt dist/SHA256SUMS dist/build-provenance.sigstore.json

python3 -m build --sdist --wheel --outdir dist .

shopt -s nullglob
sdists=(dist/audiodoc-*.tar.gz)
wheels=(dist/audiodoc-*.whl)
if [[ ${#sdists[@]} -ne 1 ]]; then
  echo "Expected exactly one source distribution in dist/, found ${#sdists[@]}." >&2
  exit 1
fi
if [[ ${#wheels[@]} -ne 1 ]]; then
  echo "Expected exactly one audiodoc wheel in dist/, found ${#wheels[@]}." >&2
  exit 1
fi

cp requirements-lock.txt dist/constraints.txt

(
  cd dist
  sha256sum "${sdists[0]##*/}" "${wheels[0]##*/}" constraints.txt > SHA256SUMS
)

printf 'Built dist/%s, dist/%s, dist/constraints.txt and dist/SHA256SUMS\n' \
  "${sdists[0]##*/}" "${wheels[0]##*/}"
