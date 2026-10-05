"""
STAGE 7 — Datasets + Experiments (the offline eval loop).

This is the payoff stage: define a fixed set of test questions once, then run
your bot against ALL of them and get scored results you can compare across
prompt/model changes.

What's new:
  - We create a Dataset 'support-qa' with a few items (input + expected).
  - We define a task() that runs one bot turn for a dataset item.
  - We define evaluator(s) that score each output (here: keyword-match accuracy
    + a length check).
  - langfuse.run_experiment(...) runs task over the dataset and uploads results.

Run it twice with different prompts/models and compare runs in
Langfuse -> Datasets -> support-qa -> Runs.

NOTE: this stage is non-interactive; just run it.
Run:  python src/stage_7_datasets_experiments.py
"""

from langfuse import get_client
from langfuse.experiment import Evaluation
from bot_core import chat_llm, MODEL_NAME, banner

langfuse = get_client()

DATASET_NAME = "support-qa"

# (question, substring we expect to see in a good answer)
SEED_ITEMS = [
    ("How do I get a refund?", "30 days"),
    ("What are your support hours?", "Mon"),
    ("I forgot my password, help", "reset"),
    ("Do you ship to Canada?", "ref"),  # not in KB -> mock returns a 'ref' filler
]


def ensure_dataset():
    try:
        langfuse.get_dataset(DATASET_NAME)
        print(f"  dataset '{DATASET_NAME}' already exists.")
    except Exception:
        langfuse.create_dataset(name=DATASET_NAME, description="Support bot smoke tests")
        for q, expected in SEED_ITEMS:
            langfuse.create_dataset_item(
                dataset_name=DATASET_NAME,
                input={"question": q},
                expected_output={"must_contain": expected},
            )
        print(f"  created dataset '{DATASET_NAME}' with {len(SEED_ITEMS)} items.")


# ── Task: how to run ONE dataset item through the bot ────────────────────
def task(*, item, **kwargs):
    question = item.input["question"]
    messages = [
        {"role": "system", "content": "You are Acme's concise support assistant."},
        {"role": "user", "content": question},
    ]
    reply, _ = chat_llm(messages)
    return reply


# ── Evaluators: score each output ────────────────────────────────────────
def contains_expected(*, input, output, expected_output, **kwargs):
    """1.0 if the expected substring appears, else 0.0."""
    must = (expected_output or {}).get("must_contain", "")
    hit = must.lower() in (output or "").lower()
    return Evaluation(name="contains-expected", value=1.0 if hit else 0.0)


def not_too_long(*, input, output, expected_output, **kwargs):
    """Penalize rambly answers; good support replies are short."""
    words = len((output or "").split())
    return Evaluation(name="concise", value=1.0 if words <= 40 else 0.0,
                      comment=f"{words} words")


def main():
    banner(7, "Datasets + Experiments")
    if not langfuse.auth_check():
        raise SystemExit("Auth failed. Check .env.")
    ensure_dataset()

    dataset = langfuse.get_dataset(DATASET_NAME)

    result = langfuse.run_experiment(
        name="support-bot-eval",
        run_name=f"run-{MODEL_NAME}",
        data=dataset.items,
        task=task,
        evaluators=[contains_expected, not_too_long],
    )

    print("\n  Experiment finished. Per-item + aggregate scores uploaded.")
    # The result object also has a readable summary you can print locally.
    try:
        print(result.format())
    except Exception:
        pass

    langfuse.flush()
    print(f"\nFlushed. Compare runs in Langfuse -> Datasets -> {DATASET_NAME} -> Runs.")
    print("Tip: change the system prompt or MODEL_NAME and run again to compare.")


if __name__ == "__main__":
    main()
