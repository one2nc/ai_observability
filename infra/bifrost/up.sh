#!/usr/bin/env sh
set -eu

if [ -z "${BIFROST_API_KEY:-}" ]; then
  echo "BIFROST_API_KEY is required" >&2
  exit 1
fi

./generate-config.sh

CONFIG_HASH="$(cksum data/config.json | awk '{print $1 ":" $2}')"
PREVIOUS_CONFIG_HASH=""
if [ -f data/config.hash ]; then
  PREVIOUS_CONFIG_HASH="$(cat data/config.hash)"
fi

if [ -f data/config.db ] && [ "$CONFIG_HASH" != "$PREVIOUS_CONFIG_HASH" ]; then
  BACKUP_SUFFIX="$(date +%Y%m%d%H%M%S)"
  mv data/config.db "data/config.db.$BACKUP_SUFFIX.bak"
  echo "Bifrost config changed; moved existing config store to data/config.db.$BACKUP_SUFFIX.bak"
fi

printf "%s\n" "$CONFIG_HASH" > data/config.hash

export BIFROST_ENCRYPTION_KEY
BIFROST_ENCRYPTION_KEY="$(cat data/encryption_key)"

docker compose up -d
