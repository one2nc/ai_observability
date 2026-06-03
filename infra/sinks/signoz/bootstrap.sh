#!/usr/bin/env bash
set -euo pipefail

SIGNOZ_REF="${SIGNOZ_REF:-main}"
TARGET_DIR="${TARGET_DIR:-../../.vendor/signoz}"

echo "==> Cloning SigNoz ref: ${SIGNOZ_REF} into ${TARGET_DIR}"

if [ -d "$TARGET_DIR/.git" ]; then
  echo "==> Repo already exists, skipping clone."
else
  git clone --depth 1 -b "$SIGNOZ_REF" https://github.com/SigNoz/signoz.git "$TARGET_DIR"
fi

echo "==> SigNoz ready at ${TARGET_DIR}"
