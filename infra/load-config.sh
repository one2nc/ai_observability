#!/usr/bin/env sh
set -eu

CONFIG_FILE="${1:-.enc}"

if [ ! -f "$CONFIG_FILE" ]; then
  cat <<'EOF'
SINK ?= signoz
AI_GATEWAY ?= none
EOF
  exit 0
fi

awk '
  function trim(s) {
    gsub(/^[[:space:]]+|[[:space:]]+$/, "", s)
    return s
  }

  function upper(s) {
    return toupper(s)
  }

  function normalize_key(key) {
    key = upper(trim(key))
    gsub(/[-.]/, "_", key)
    if (key == "GATEWAY" || key == "AI_GATEWAY_ENABLED" || key == "BIFROST_ENABLED") {
      return "AI_GATEWAY"
    }
    if (key == "PROVIDER") {
      return "BIFROST_PROVIDER"
    }
    if (key == "API_TOKEN" || key == "API_KEY" || key == "TOKEN" || key == "BIFROST_API_TOKEN") {
      return "BIFROST_API_KEY"
    }
    return key
  }

  function normalize_value(key, value) {
    value = trim(value)
    gsub(/^["'\''"]|["'\''"]$/, "", value)
    lower = tolower(value)
    if (key == "AI_GATEWAY") {
      if (lower == "true" || lower == "yes" || lower == "enabled" || lower == "bifrost") {
        return "bifrost"
      }
      if (lower == "false" || lower == "no" || lower == "disabled" || lower == "none") {
        return "none"
      }
    }
    return value
  }

  /^[[:space:]]*($|#)/ { next }

  {
    line = $0
    sub(/[[:space:]]+#.*$/, "", line)
    if (index(line, "=") > 0) {
      split(line, parts, "=")
      key = parts[1]
      value = substr(line, index(line, "=") + 1)
    } else if (index(line, ":") > 0) {
      split(line, parts, ":")
      key = parts[1]
      value = substr(line, index(line, ":") + 1)
    } else {
      next
    }

    key = normalize_key(key)
    value = normalize_value(key, value)
    if (key != "" && value != "") {
      print key " ?= " value
    }
  }
' "$CONFIG_FILE"
