# Failure Modes & Personas — 03_openllmetry_manual

## Personas

| Persona | What they care about | What the current setup gives them |
|---------|---------------------|----------------------------------|
| Platform/SRE | Is the service up? Is it slow? | HTTP spans, latency histograms, error rates |
| FinOps | How much are we spending on LLMs? Per user? | `gen_ai.client.token.usage` + `user.id` attribute for per-user cost slicing |
| ML/AI Engineer | Is the RAG pipeline working correctly? Are retrievals relevant? | Full pipeline spans + similarity scores (min/max/avg) per retrieval |
| Product Manager | How long do users wait for answers? | End-to-end `/ask` latency with breakdown (embed vs retrieve vs generate) |
| Security/Compliance | What prompts/data are being sent to LLMs? | OpenLLMetry captures prompt/completion content + user.id for audit |

## Failure modes

| Failure mode | Signal | Auto-instrumented? | Manual work needed | Status in 03 |
|---|---|---|---|---|
| LLM provider down/slow | `gen_ai.client.operation.duration` spikes | ✅ Yes | None | ✅ Covered |
| Embedding API failure | `openai.embeddings` span error | ✅ Yes | None | ✅ Covered |
| Token budget blown | `gen_ai.client.token.usage` exceeds threshold | ✅ Yes | Set up alert | ✅ Covered |
| Prompt injection / abuse | Large token counts per request | ✅ Yes | Correlate with user.id | ✅ Covered |
| Cost runaway | Token rate vs request rate divergence | ✅ Yes | Set up alert | ✅ Covered |
| **Instrumentable gaps (now closed)** | | | | |
| Database connection failure | `rag.ask` span errors before LLM call | ✅ Manual span | Added in 03 | ✅ Covered |
| Bad retrieval (no relevant docs) | `retrieve.similarity_avg` below threshold | ✅ Manual span | Added in 03 | ✅ Covered |
| Per-user cost attribution | `user.id` on `rag.ask` span | ✅ Manual attribute | Added in 03 | ✅ Covered |
| **Evaluation problems (still open)** | | | | |
| Model degradation | Same prompts, worse output quality | ❌ No | Needs eval layer | ❌ Not covered |
| Hallucination | LLM ignores context | ❌ No | Needs eval layer | ❌ Not covered |
| Bad chunking | Poor answers due to bad chunk boundaries | ❌ No | Needs retrieval eval | ❌ Not covered |

## What changed from 02 to 03

The three "instrumentable gaps" from 02 are now closed:
1. **DB/retrieval visibility** — `rag.retrieve` and `rag.vector_search` spans show pgvector query timing
2. **Retrieval quality signal** — `retrieve.similarity_avg/min/max` attributes enable alerting on bad retrievals
3. **Per-user attribution** — `user.id` attribute enables per-user cost dashboards and abuse detection

## Remaining gaps (require eval, not observability)

Model degradation, hallucination, and bad chunking require ground truth or human judgment. These are evaluation problems, not instrumentation problems. A future experiment could add LLM-as-judge scoring as a custom metric.
