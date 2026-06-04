#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-8004}"
BASE_URL="${BASE_URL:-http://localhost:${PORT}}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="${DATA_DIR:-${ROOT_DIR}/sample_data}"
EXPERIMENT_DIR="${EXPERIMENT_DIR:-${ROOT_DIR}/experiment_data}"
QUESTIONS_FILE="${QUESTIONS_FILE:-${EXPERIMENT_DIR}/sample_questions.txt}"
USERS_FILE="${USERS_FILE:-${EXPERIMENT_DIR}/sample_users.txt}"
CHAT_MODELS_FILE="${CHAT_MODELS_FILE:-${EXPERIMENT_DIR}/sample_chat_models.txt}"

usage() {
  printf 'Usage: %s ingest|ask|traffic [count]\n' "$0" >&2
  printf '  ingest  Randomly ingest one or more sample_data/*.txt files\n' >&2
  printf '  ask     Ask one or more random questions with random user_id and chat_model values\n' >&2
  printf '  traffic Randomly mix ingest and ask calls\n' >&2
}

random_uint() {
  od -An -N4 -tu4 /dev/urandom | tr -d ' '
}

random_index() {
  local size="$1"
  local value
  value="$(random_uint)"
  printf '%s\n' "$((value % size))"
}

json_string() {
  python3 -c 'import json, sys; print(json.dumps(sys.stdin.read().rstrip("\n")))'
}

files=()
questions=()
users=()
chat_models=()

load_questions() {
  questions=()
  while IFS= read -r line || [ -n "$line" ]; do
    [ -n "$line" ] && questions+=("$line")
  done < "$QUESTIONS_FILE"
}

load_users() {
  users=()
  while IFS= read -r line || [ -n "$line" ]; do
    [ -n "$line" ] && users+=("$line")
  done < "$USERS_FILE"
}

load_chat_models() {
  chat_models=()
  [ -f "$CHAT_MODELS_FILE" ] || return 0
  while IFS= read -r line || [ -n "$line" ]; do
    [ -n "$line" ] && chat_models+=("$line")
  done < "$CHAT_MODELS_FILE"
}

load_files() {
  files=()
  while IFS= read -r file; do
    files+=("$file")
  done < <(find "$DATA_DIR" -type f -name '*.txt' -print | sort)
}

pick_file() {
  local idx
  if [ "${#files[@]}" -eq 0 ]; then
    printf 'No sample files found in %s\n' "$DATA_DIR" >&2
    exit 1
  fi
  idx="$(random_index "${#files[@]}")"
  printf '%s\n' "${files[$idx]}"
}

pick_question() {
  local idx
  if [ "${#questions[@]}" -eq 0 ]; then
    printf 'No questions found in %s\n' "$QUESTIONS_FILE" >&2
    exit 1
  fi
  idx="$(random_index "${#questions[@]}")"
  printf '%s\n' "${questions[$idx]}"
}

pick_user() {
  local idx
  if [ "${#users[@]}" -eq 0 ]; then
    printf 'No users found in %s\n' "$USERS_FILE" >&2
    exit 1
  fi
  idx="$(random_index "${#users[@]}")"
  printf '%s\n' "${users[$idx]}"
}

pick_chat_model() {
  local idx
  if [ "${#chat_models[@]}" -eq 0 ]; then
    printf '\n'
    return 0
  fi
  idx="$(random_index "${#chat_models[@]}")"
  printf '%s\n' "${chat_models[$idx]}"
}

print_response() {
  local body_file="$1"
  if ! python3 -m json.tool < "$body_file" 2>/dev/null; then
    cat "$body_file"
  fi
}

post_form() {
  local url="$1"
  local form_arg="$2"
  local body_file status
  body_file="$(mktemp)"
  status="$(curl -sS -w '%{http_code}' -o "$body_file" -X POST "$url" -F "$form_arg")" || {
    cat "$body_file" >&2
    rm -f "$body_file"
    return 1
  }
  print_response "$body_file"
  rm -f "$body_file"
  if [ "$status" -lt 200 ] || [ "$status" -ge 300 ]; then
    printf 'HTTP %s from %s\n' "$status" "$url" >&2
    return 1
  fi
}

post_json() {
  local url="$1"
  local payload="$2"
  local body_file status
  body_file="$(mktemp)"
  status="$(curl -sS -w '%{http_code}' -o "$body_file" -X POST "$url" -H "Content-Type: application/json" -d "$payload")" || {
    cat "$body_file" >&2
    rm -f "$body_file"
    return 1
  }
  print_response "$body_file"
  rm -f "$body_file"
  if [ "$status" -lt 200 ] || [ "$status" -ge 300 ]; then
    printf 'HTTP %s from %s\n' "$status" "$url" >&2
    return 1
  fi
}

do_ingest() {
  local file
  file="$(pick_file)"
  printf '\n[ingest] %s\n' "$(basename "$file")" >&2
  post_form "${BASE_URL}/ingest" "file=@${file}"
}

do_ask() {
  local question user chat_model escaped_question escaped_user escaped_chat_model payload
  question="$(pick_question)"
  user="$(pick_user)"
  chat_model="$(pick_chat_model)"
  escaped_question="$(printf '%s' "$question" | json_string)"
  escaped_user="$(printf '%s' "$user" | json_string)"
  payload="{\"query\": ${escaped_question}, \"user_id\": ${escaped_user}}"
  if [ -n "$chat_model" ]; then
    escaped_chat_model="$(printf '%s' "$chat_model" | json_string)"
    payload="{\"query\": ${escaped_question}, \"user_id\": ${escaped_user}, \"chat_model\": ${escaped_chat_model}}"
  fi
  printf '\n[ask] user=%s model=%s question=%s\n' "$user" "${chat_model:-default}" "$question" >&2
  post_json "${BASE_URL}/ask" "$payload"
}

mode="${1:-}"
count="${2:-1}"

if [ -z "$mode" ] || [ "$mode" = "-h" ] || [ "$mode" = "--help" ]; then
  usage
  exit 0
fi

if ! [[ "$count" =~ ^[0-9]+$ ]] || [ "$count" -lt 1 ]; then
  printf 'count must be a positive integer\n' >&2
  exit 1
fi

load_files
load_questions
load_users
load_chat_models

case "$mode" in
  ingest)
    for _ in $(seq 1 "$count"); do
      do_ingest
    done
    ;;
  ask)
    for _ in $(seq 1 "$count"); do
      do_ask
    done
    ;;
  traffic)
    for _ in $(seq 1 "$count"); do
      if [ "$(random_index 100)" -lt 35 ]; then
        do_ingest || true
      else
        do_ask || true
      fi
    done
    ;;
  *)
    usage
    exit 1
    ;;
esac
