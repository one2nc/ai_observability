#!/usr/bin/env python3
"""Generate random RAG traffic (ingest/ask) against the bifrost experiment app."""

import argparse
import json
import logging
import os
import random
import sys
from pathlib import Path

import requests
import yaml


def load_args() -> dict:
    """Parse CLI arguments and return as dictionary."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["ingest", "ask", "traffic"], help="Operation mode")
    parser.add_argument("--count", type=int, default=1, help="Number of operations")
    parser.add_argument("--port", default=os.environ.get("PORT", "8004"), help="App port")
    parser.add_argument("--base-url", default=os.environ.get("BASE_URL", ""), help="App base URL")
    parser.add_argument("--log-level", default=os.environ.get("LOG_LEVEL", "INFO"), help="Log level")
    return vars(parser.parse_args())


def validate_args(args: dict) -> bool:
    """Validate arguments, return True if valid."""
    if args["count"] < 1:
        logging.error("status=validation_failed reason=count_must_be_positive")
        return False
    return True


def update_args(args: dict) -> bool:
    """Process/enhance arguments, return True if successful."""
    if not args["base_url"]:
        args["base_url"] = f"http://localhost:{args['port']}"
    args["root_dir"] = Path(__file__).resolve().parent.parent
    args["data_dir"] = args["root_dir"] / "sample_data"
    args["experiment_dir"] = args["root_dir"] / "experiment_data"
    return True


def load_yaml_list(path: Path) -> list[str]:
    """Load a YAML file that contains a plain list."""
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text())
    if isinstance(data, list):
        return data
    return []


def load_files(data_dir: Path) -> list[Path]:
    """Find all .txt files in sample_data."""
    return sorted(data_dir.glob("*.txt"))


def do_ingest(base_url: str, files: list[Path]) -> dict | None:
    """Ingest a random file. Returns response JSON on success, None on failure."""
    f = random.choice(files)
    logging.info("action=ingest file=%s", f.name)
    resp = requests.post(f"{base_url}/ingest", files={"file": (f.name, f.open("rb"))})
    if resp.ok:
        return resp.json()
    logging.error("status=ingest_failed http_status=%d body=%s", resp.status_code, resp.text)
    return None


def do_ask(base_url: str, questions: list[str], users: list[str], models: list[str]) -> dict | None:
    """Ask a random question with random user and model. Returns response JSON on success, None on failure."""
    payload: dict = {
        "query": random.choice(questions),
        "user_id": random.choice(users),
        "chat_model": random.choice(models),
    }
    logging.info("action=ask user=%s model=%s question=%s", payload["user_id"], payload["chat_model"], payload["query"])
    resp = requests.post(f"{base_url}/ask", json=payload)
    if resp.ok:
        return resp.json()
    logging.error("status=ask_failed http_status=%d body=%s", resp.status_code, resp.text)
    return None


def main() -> int:
    """Main function returning exit code."""
    args = load_args()
    logging.basicConfig(
        level=args["log_level"],
        format="%(asctime)s.%(msecs)03d %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stderr,
    )

    if not validate_args(args):
        return 1

    if not update_args(args):
        return 1

    files = load_files(args["data_dir"])
    questions = load_yaml_list(args["experiment_dir"] / "sample_questions.yaml")
    users = load_yaml_list(args["experiment_dir"] / "sample_users.yaml")
    models = load_yaml_list(args["experiment_dir"] / "sample_chat_models.yaml")

    if not files:
        logging.error("status=no_files dir=%s", args["data_dir"])
        return 1

    if not questions:
        logging.error("status=no_questions file=%s", args["experiment_dir"] / "sample_questions.yaml")
        return 1

    if not users:
        logging.error("status=no_users file=%s", args["experiment_dir"] / "sample_users.yaml")
        return 1

    models_file = args["experiment_dir"] / "sample_chat_models.yaml"
    if not models_file.exists():
        logging.error(
            "status=no_models file=%s msg=File not found. Run: cp %s.example %s",
            models_file, models_file, models_file,
        )
        return 1

    if not models:
        logging.error(
            "status=no_models file=%s msg=Uncomment the models you want to use. Each model incurs token costs - choose deliberately.",
            models_file,
        )
        return 1

    base_url = args["base_url"]
    mode = args["mode"]

    for _ in range(args["count"]):
        result = None

        if mode == "ingest":
            result = do_ingest(base_url, files)
        elif mode == "ask":
            result = do_ask(base_url, questions, users, models)
        elif mode == "traffic":
            # 35% ingests, 65% asks — simulates realistic read-heavy traffic mix
            if random.random() < 0.35:
                result = do_ingest(base_url, files)
            else:
                result = do_ask(base_url, questions, users, models)

        if result is None:
            return 1

        print(json.dumps(result, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
