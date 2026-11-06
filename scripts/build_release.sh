#!/usr/bin/env bash
set -euo pipefail

VERSION="${1:?usage: build_release.sh VERSION}"

if [[ ! "$VERSION" =~ ^[0-9A-Za-z][0-9A-Za-z.+-]*$ ]]; then
  echo "Invalid release version: $VERSION" >&2
  exit 2
fi

NAME="audiodoc-${VERSION}"
mkdir -p dist
rm -f dist/audiodoc-*.zip dist/SHA256SUMS

git archive --format=zip --prefix="${NAME}/" -o "dist/${NAME}.zip" HEAD \
  app.py backend deploy docs requirements.txt requirements-lock.txt \
  .env.example install.sh README.md README.ru.md LICENSE

(
  cd dist
  sha256sum "${NAME}.zip" > SHA256SUMS
)

printf 'Built dist/%s.zip and dist/SHA256SUMS\n' "$NAME"
