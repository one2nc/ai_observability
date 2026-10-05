"""
STAGE 3 — Nested spans (multi-step trace).

Real bots do more than one LLM call per turn. Here we simulate a tiny RAG flow:
    retrieve-context (span)  ->  llm-response (generation)
Both nested under the chat-turn trace. Now the trace is a tree and you can see
which step is slow or where a bad answer came from.

What's new:
  - A child "span" for retrieval (non-LLM work).
  - The generation nests under the same turn automatically via OTEL context.

After running, open a trace in Langfuse: you'll see the hierarchy and per-step
latency.

Run:  python src/stage_3_nested_spans.py
"""

import time
import uuid

from langfuse import get_client, observe, propagate_attributes
from bot_core import chat_llm, SYSTEM_PROMPT_FALLBACK, MODEL_NAME, banner

langfuse = get_client()
SESSION_ID = f"chat-{uuid.uuid4().hex[:8]}"

# A tiny fake knowledge base.
KB = {
    "refund": "Refunds are available within 30 days via the Orders page.",
    "hours": "Support hours: Mon-Fri, 9am-6pm.",
    "password": "Reset via 'Forgot password' on the login screen.",
}


def retrieve_context(query):
    """Fake retrieval: matches keywords, returns snippets. Traced as a span."""
    with langfuse.start_as_current_observation(
        as_type="span",
        name="retrieve-context",
        input={"query": query},
    ) as span:
        time.sleep(0.05)  # pretend vector search latency
        hits = [v for k, v in KB.items() if k in query.lower()]
        span.update(output={"hits": hits, "n": len(hits)})
        return hits


@observe(name="chat-turn")
def handle_turn(history, user_query):
    with propagate_attributes(session_id=SESSION_ID, user_id="demo-user", tags=["stage-3", "rag"]):
        # Step 1: retrieval (child span)
        context = retrieve_context(user_query)

        # Inject retrieved context into the system message.
        augmented = list(history)
        if context:
            augmented.insert(1, {"role": "system", "content": "Context: " + " ".join(context)})

        # Step 2: generation (child generation)
        with langfuse.start_as_current_observation(
            as_type="generation",
            name="llm-response",
            model=MODEL_NAME,
            input=augmented,
        ) as gen:
            reply, usage = chat_llm(augmented)
            gen.update(
                output=reply,
                usage_details={"input": usage["input"], "output": usage["output"]},
            )
    return reply


def main():
    banner(3, "Nested spans (retrieve -> generate)")
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
        reply = handle_turn(history, user)
        history.append({"role": "assistant", "content": reply})
        print(f"bot > {reply}")

    langfuse.flush()
    print("\nFlushed. Open a trace -> see retrieve-context and llm-response nested.")


if __name__ == "__main__":
    main()
