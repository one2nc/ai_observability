# Failure Modes — openllmetry_manual

| # | Failure mode | Layer | Why? | How? | Where? | What? |
|---|---|---|---|---|---|---|
| 1 | App is slow | Application | Identify bottleneck step | Compare request p95 with LLM duration | FastAPI → Request Duration p95 vs OpenLLMetry → LLM Call Duration | `http.server.duration` vs `gen_ai.client.operation.duration` — e.g. if LLM duration is 80% of request duration, the model is the bottleneck, not your code |
| 2 | App errors (5xx) | Application | Detect crashes | Alert when 5xx rate > 0 | FastAPI → Error Rate (5xx) | `http.server.duration{status=5xx}` |
| 3 | App saturation | Application | Prevent queuing | Alert when active requests stays high | FastAPI → Active Requests | `http.server.active_requests` |
| 4 | Database connection failure | Application | Avoid silent retrieval failures | Span errors before `rag.retrieve` | Trace explorer | `rag.ask` span error |
| 5 | **Bad retrieval (irrelevant docs)** | Retrieval | Prevent poor answers | Alert when p50 similarity drops | Manual → Retrieval Similarity (p50/p95) | `rag_retrieve_similarity_score` |
| 6 | Knowledge base gaps | Retrieval | Detect missing documents | Alert when empty retrievals rise | Manual → Empty Retrievals | `rag_retrieve_empty` |
| 7 | LLM provider down/slow | Provider | Avoid timeouts, trigger failover | Alert when p95 exceeds threshold | OpenLLMetry → LLM Call Duration (p95) | `gen_ai.client.operation.duration` |
| 8 | Embedding API failure | Provider | Prevent silent search degradation | Filter traces by error status | Trace explorer | `openai.embeddings` span error |
| 9 | Token budget blown | Model | Control costs before bill shock | Alert when token rate exceeds budget | OpenLLMetry → Token Usage Rate | `gen_ai.client.token.usage` |
| 10 | Cost runaway | Model | Catch runaway loops | Token rate growing faster than request rate | OpenLLMetry → Token Usage Rate vs FastAPI → Request Rate | `sum(rate(gen_ai_client_token_usage_sum[1m])) / sum(rate(http_server_duration_milliseconds_count[1m]))` — e.g. RAG returning more docs per query inflates prompt tokens |
| 11 | **Per-user abuse** | User | Identify who is abusing | Group traces by `user.id` | Trace explorer | `user.id` on `rag.ask` span |
| | **Not detectable** | | | | | |
| 12 | Bad chunking | Retrieval | — | — | — | Needs retrieval eval |
| 13 | Model degradation | Model | — | — | — | Needs eval layer |
| 14 | Hallucination | Model | — | — | — | Needs eval layer |
