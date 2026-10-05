"""
STAGE 0 — Plain chatbot. NO Langfuse.

Purpose: feel the blindness. You get replies, but you have zero visibility
into latency, token cost, what the user said three turns ago, or whether
the answer was any good. Every later stage fixes one piece of this.

Run:  python src/stage_0_plain_bot.py
Type 'quit' to exit.
"""

from bot_core import chat_llm, SYSTEM_PROMPT_FALLBACK, banner


def main():
    banner(0, "Plain chatbot (no observability)")
    history = [{"role": "system", "content": SYSTEM_PROMPT_FALLBACK}]

    while True:
        user = input("\nyou > ").strip()
        if user.lower() in {"quit", "exit"}:
            break
        if not user:
            continue

        history.append({"role": "user", "content": user})
        reply, usage = chat_llm(history)
        history.append({"role": "assistant", "content": reply})

        print(f"bot > {reply}")
        # This print is the ONLY visibility you have right now.
        print(f"      (tokens in/out: {usage['input']}/{usage['output']})")


if __name__ == "__main__":
    main()
