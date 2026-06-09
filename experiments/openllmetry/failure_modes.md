# Failure Modes & Personas — openllmetry

## Personas

| Persona | What they care about | What the current setup gives them |
|---------|---------------------|----------------------------------|
| Platform/SRE | Is the service up? Is it slow? | HTTP spans, latency histograms, error rates |
| FinOps | How much are we spending on LLMs? | `gen_ai.client.token.usage` — track cost per model |
| ML/AI Engineer | Is the RAG pipeline working correctly? Are retrievals relevant? | Embed and generate timing only. Retrieval step (pgvector query, similarity scores) is NOT visible — requires manual spans (see otel) or custom metrics |
| Product Manager | How long do users wait for answers? | End-to-end `/ask` latency |
| Security/Compliance | What prompts/data are being sent to LLMs? | OpenLLMetry captures prompt/completion content (can be disabled) |

## Failure modes catchable with this setup

| Failure mode | Signal | Auto-instrumented? | Manual work needed | Where to see it |
|---|---|---|---|---|
| LLM provider down/slow | `gen_ai.client.operation.duration` spikes or errors | ✅ Yes | None | Duration panel, trace spans with errors |
| Embedding API failure | `openai.embeddings` span with error status | ✅ Yes | None | Traces tab, filter by status=error |
| Token budget blown | `gen_ai.client.token.usage` exceeds threshold | ✅ Yes | Set up alert | Metrics alert on token rate |
| Prompt injection / abuse | Unusually large token counts per request | ✅ Yes (token count) | Correlate with per-request context | Token usage spikes, prompt content in traces |
| Cost runaway | Token rate increasing without request increase | ✅ Yes | Set up alert on divergence | Token rate vs request rate |
| **Instrumentable gaps** | | | | |
| Database connection failure | `rag.ask` span errors out before LLM call | ❌ No | Add span around DB call | Not visible without manual span |
| Bad retrieval (no relevant docs) | Low similarity scores, poor answers | ❌ No | Emit similarity as span attribute or custom metric | Requires manual instrumentation in retrieve() |
| Per-user cost attribution | Can't tell which user is burning tokens | ❌ No | Add user_id as span/metric attribute | Not possible without custom attributes |
| **Evaluation problems** | | | | |
| Model degradation | Same prompts, worse output quality | ❌ No | Needs eval metrics / LLM-as-judge | Not catchable with observability alone |
| Hallucination | LLM ignores context and makes things up | ❌ No | Needs eval layer (LLM-as-judge, ground truth) | Not catchable with observability alone |
| Bad chunking | Poor answers due to irrelevant or split chunks | ❌ No | Needs retrieval eval metrics (precision/recall) | Not catchable with observability alone |

## Observability vs Evaluation boundary

The failure modes marked ❌ fall into two categories:
- **Instrumentable gaps** (DB connection, bad retrieval, per-user cost): these *could* be caught with richer instrumentation — manual spans, custom metrics, or a tool that auto-instruments your vector DB client.
- **Evaluation problems** (model degradation, hallucination, bad chunking): these require ground truth or human judgment, not just telemetry. No observability tool can solve them alone.
