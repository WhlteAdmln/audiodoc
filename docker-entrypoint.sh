#!/bin/sh
set -eu

unset AUDIODOC_AUDIO_KEY
unset AUDIODOC_DOCUMENT_KEY

if [ "${1:-}" != "audiodoc" ]; then
    set -- audiodoc "$@"
fi

exec "$@"
