# Failure Modes — openllmetry

| # | Failure mode | Layer | Why? | How? | Where? | What? |
|---|---|---|---|---|---|---|
| 1 | App is slow | Application | Identify if latency is app-side or LLM-side | Compare request p95 with LLM duration p95 | FastAPI → Request Duration p95 vs OpenLLMetry → LLM Call Duration | `http.server.duration` vs `gen_ai.client.operation.duration` |
| 2 | App errors (5xx) | Application | Detect crashes, unhandled exceptions | Alert when 5xx rate > 0 | FastAPI → Error Rate (5xx) | `http.server.duration{http_status_code=~"5.."}` |
| 3 | App saturation | Application | Prevent request queuing, scale up | Alert when active requests stays high | FastAPI → Active Requests | `http.server.active_requests` |
| 4 | **LLM provider down/slow** | Provider | Avoid user-facing timeouts | Alert when p95 duration exceeds threshold | OpenLLMetry → LLM Call Duration (p95) | `gen_ai.client.operation.duration` |
| 5 | Embedding API failure | Provider | Prevent silent search degradation | Filter traces by error status | Trace explorer | `openai.embeddings` span with error status |
| 6 | **Token budget blown** | Model | Control costs before bill shock | Alert when token rate exceeds budget | OpenLLMetry → Token Usage Rate | `gen_ai.client.token.usage` |
| 7 | Cost runaway | Model | Catch runaway loops or inefficient prompts | Token rate growing faster than request rate | OpenLLMetry → Token Usage Rate vs FastAPI → Request Rate | `sum(rate(gen_ai_client_token_usage_sum[1m])) / sum(rate(http_server_duration_milliseconds_count[1m]))` — e.g. RAG returning more docs per query inflates prompt tokens |
| | **Not detectable** | | | | | |
| 8 | Database connection failure | Application | — | — | — | No span around DB call |
| 9 | Bad retrieval (no relevant docs) | Retrieval | — | — | — | No similarity scores captured |
| 10 | Bad chunking | Retrieval | — | — | — | Needs retrieval eval |
| 11 | Model degradation | Model | — | — | — | Needs eval layer |
| 12 | Hallucination | Model | — | — | — | Needs eval layer |
| 13 | Per-user cost attribution | User | — | — | — | No `user.id` on spans/metrics |
