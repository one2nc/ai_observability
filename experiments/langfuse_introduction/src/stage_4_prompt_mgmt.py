"""
STAGE 4 — Prompt Management.

Move the system prompt OUT of code and into Langfuse, where it can be
versioned and edited in the UI without redeploying.

What's new:
  - On first run we create a prompt named "support-system-prompt" (if missing).
  - Each turn fetches it with langfuse.get_prompt(...) (cached, low latency).
  - We pass `prompt=` to the generation so the trace LINKS to the prompt
    version. Later you can compare versions by cost/latency/scores.

Try this: after one run, go to Langfuse -> Prompts, edit the prompt text,
save a new version, then run again — no code change needed.

Run:  python src/stage_4_prompt_mgmt.py
"""

import uuid

from langfuse import get_client, observe, propagate_attributes
from bot_core import chat_llm, MODEL_NAME, banner

langfuse = get_client()
SESSION_ID = f"chat-{uuid.uuid4().hex[:8]}"
PROMPT_NAME = "support-system-prompt"


def ensure_prompt():
    """Create the prompt in Langfuse if it doesn't exist yet."""
    try:
        langfuse.get_prompt(PROMPT_NAME)
        print(f"  prompt '{PROMPT_NAME}' already exists in Langfuse.")
    except Exception:
        langfuse.create_prompt(
            name=PROMPT_NAME,
            prompt="You are Acme's support assistant. Be concise, warm, and accurate. "
                   "If unsure, say so and offer to escalate.",
            labels=["production"],   # marks this version as the one to fetch
            type="text",
            commit_message="initial version",
        )
        print(f"  created prompt '{PROMPT_NAME}' (label: production).")


@observe(name="chat-turn")
def handle_turn(history_user_msgs):
    with propagate_attributes(session_id=SESSION_ID, user_id="demo-user", tags=["stage-4"]):
        # Fetch the managed prompt (uses 'production' label).
        prompt_client = langfuse.get_prompt(PROMPT_NAME, label="production")
        system_text = prompt_client.compile()  # no variables here, returns text

        messages = [{"role": "system", "content": system_text}] + history_user_msgs

        with langfuse.start_as_current_observation(
            as_type="generation",
            name="llm-response",
            model=MODEL_NAME,
            input=messages,
            prompt=prompt_client,   # <-- links this generation to the prompt version
        ) as gen:
            reply, usage = chat_llm(messages)
            gen.update(
                output=reply,
                usage_details={"input": usage["input"], "output": usage["output"]},
            )
    return reply


def main():
    banner(4, "Prompt Management")
    if not langfuse.auth_check():
        raise SystemExit("Auth failed. Check .env.")
    ensure_prompt()

    convo = []  # only user/assistant turns; system comes from Langfuse
    while True:
        user = input("\nyou > ").strip()
        if user.lower() in {"quit", "exit"}:
            break
        if not user:
            continue
        convo.append({"role": "user", "content": user})
        reply = handle_turn(convo)
        convo.append({"role": "assistant", "content": reply})
        print(f"bot > {reply}")

    langfuse.flush()
    print("\nFlushed. Edit the prompt in Langfuse -> Prompts, then re-run to see versioning.")


if __name__ == "__main__":
    main()
