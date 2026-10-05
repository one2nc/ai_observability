"""
STAGE 2 — Sessions + Users.

A chatbot is multi-turn, but Stage 1 produced disconnected traces. Here we
attach a session_id and user_id so Langfuse stitches a whole conversation
together.

What's new:
  - One session_id per program run (uuid).
  - A user_id you can set via env (defaults to 'demo-user').
  - propagate_attributes() wraps each turn so EVERY observation in the trace
    inherits these IDs. Call it early, inside the trace.

After running, open Langfuse -> Sessions to replay the whole conversation,
and filter Traces by user.

Run:  python src/stage_2_sessions.py
"""

import os
import uuid

from langfuse import get_client, observe, propagate_attributes
from bot_core import chat_llm, SYSTEM_PROMPT_FALLBACK, MODEL_NAME, banner

langfuse = get_client()

SESSION_ID = f"chat-{uuid.uuid4().hex[:8]}"
USER_ID = os.getenv("DEMO_USER_ID", "demo-user")


@observe(name="chat-turn")
def handle_turn(history):
    # Propagate session/user across all child observations of this trace.
    with propagate_attributes(
        session_id=SESSION_ID,
        user_id=USER_ID,
        tags=["stage-2", "support-bot"],
    ):
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
    banner(2, "Sessions + Users")
    if not langfuse.auth_check():
        raise SystemExit("Auth failed. Check .env.")
    print(f"  session_id = {SESSION_ID}   user_id = {USER_ID}")

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

    langfuse.flush()
    print(f"\nFlushed. Open Langfuse -> Sessions and find session '{SESSION_ID}'.")


if __name__ == "__main__":
    main()
