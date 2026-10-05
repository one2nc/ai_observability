"""
STAGE 5 — Scores (user feedback).

Add a thumbs up/down after each reply and push it to Langfuse as a SCORE
on that trace. This is your first quality signal; it shows on the trace and
aggregates in dashboards.

What's new:
  - After each bot reply we ask the user to rate it.
  - We capture the trace id and call score_current_trace() BEFORE the trace
    closes (so it attaches to the right turn).

After running, open a trace -> see the 'user-feedback' score. Dashboards then
chart average feedback over time.

Run:  python src/stage_5_user_feedback.py
"""

import uuid

from langfuse import get_client, observe, propagate_attributes
from bot_core import chat_llm, SYSTEM_PROMPT_FALLBACK, MODEL_NAME, banner

langfuse = get_client()
SESSION_ID = f"chat-{uuid.uuid4().hex[:8]}"


@observe(name="chat-turn")
def handle_turn(history):
    """Returns (reply, trace_id) so the caller can score this exact turn."""
    with propagate_attributes(session_id=SESSION_ID, user_id="demo-user", tags=["stage-5"]):
        with langfuse.start_as_current_observation(
            as_type="generation", name="llm-response", model=MODEL_NAME, input=history
        ) as gen:
            reply, usage = chat_llm(history)
            gen.update(
                output=reply,
                usage_details={"input": usage["input"], "output": usage["output"]},
            )
        trace_id = langfuse.get_current_trace_id()
        return reply, trace_id


def main():
    banner(5, "Scores (user feedback)")
    if not langfuse.auth_check():
        raise SystemExit("Auth failed. Check .env.")

    history = [{"role": "system", "content": SYSTEM_PROMPT_FALLBACK}]
    while True:
        user = input("\nyou > ").strip()
        if user.lower() in {"quit", "exit"}:
            break
        if not user:
            continue
        history.append({"role": "user", "content": user})
        reply, trace_id = handle_turn(history)
        history.append({"role": "assistant", "content": reply})
        print(f"bot > {reply}")

        rating = input("      rate this reply [u]p / [d]own / enter to skip: ").strip().lower()
        if rating in {"u", "d"}:
            # BOOLEAN score: 1 = good, 0 = bad. Attach by trace_id.
            langfuse.create_score(
                trace_id=trace_id,
                name="user-feedback",
                value=1 if rating == "u" else 0,
                data_type="BOOLEAN",
                comment="thumbs up" if rating == "u" else "thumbs down",
            )
            print("      recorded.")

    langfuse.flush()
    print("\nFlushed. Open traces -> see 'user-feedback' scores; check Dashboards for aggregates.")


if __name__ == "__main__":
    main()
