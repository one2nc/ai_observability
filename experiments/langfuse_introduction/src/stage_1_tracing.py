"""
STAGE 1 — Tracing (the core feature).

What's new vs Stage 0:
  - We wrap each chat turn in @observe() so Langfuse records a TRACE.
  - Inside, we open a "generation" observation for the LLM call and record
    the model, input messages, output text, and token usage.

After running, open http://localhost:3000 -> Tracing. Each turn is one trace.
Click into it to see latency, the exact messages, and token/cost numbers.

Run:  python src/stage_1_tracing.py
"""

from langfuse import get_client, observe
from bot_core import chat_llm, SYSTEM_PROMPT_FALLBACK, MODEL_NAME, banner

langfuse = get_client()


@observe(name="chat-turn")  # creates the trace for one user turn
def handle_turn(history):
    # Open a generation observation = the LLM call specifically.
    with langfuse.start_as_current_observation(
        as_type="generation",
        name="llm-response",
        model=MODEL_NAME,
        input=history,
    ) as gen:
        reply, usage = chat_llm(history)
        gen.update(
            output=reply,
            usage_details={"input": usage["input"], "output": usage["output"]},
        )
    return reply


def main():
    banner(1, "Tracing with @observe + generation")
    if not langfuse.auth_check():
        raise SystemExit("Auth failed. Check .env keys/host point at your local Langfuse.")

    history = [{"role": "system", "content": SYSTEM_PROMPT_FALLBACK}]
    while True:
        user = input("\nyou > ").strip()
        if user.lower() in {"quit", "exit"}:
            break
        if not user:
            continue

        history.append({"role": "user", "content": user})
        reply = handle_turn(history)
        history.append({"role": "assistant", "content": reply})
        print(f"bot > {reply}")

    langfuse.flush()  # push buffered traces before exit
    print("\nFlushed. See your traces at http://localhost:3000 -> Tracing")


if __name__ == "__main__":
    main()
