# Failure Modes — bifrost

| # | Failure mode | Layer | Why? | How? | Where? | What? |
|---|---|---|---|---|---|---|
| 1 | App is slow | Application | Identify if latency is app-side or LLM-side | Compare Request Duration p95 with OpenLLMetry Operation Duration | FastAPI → Request Duration p95 vs OpenLLMetry → Operation Duration | `histogram_quantile(0.95, sum(rate(http_server_duration_milliseconds_bucket[1m])) by (le))` vs `gen_ai_client_operation_duration_seconds` p50 |
| 2 | App errors (5xx) | Application | Detect crashes, unhandled exceptions | Error Rate (5xx) panel shows non-zero | FastAPI → Error Rate (5xx) | `sum(rate(http_server_duration_milliseconds_count{http_status_code=~"5.."}[1m]))` > 0 |
| 3 | App saturation | Application | Prevent request queuing | Active Requests stays high | FastAPI → Active Requests | `http_server_active_requests` sustained > threshold |
| 4 | Database connection failure | Application | Avoid silent retrieval failures | `rag.ask` span errors before LLM call; retrieval count drops | Manual spans + Manual → Retrieval Count Rate | `rate(rag_retrieve_count_total[1m])` drops to 0 while `rate(http_server_duration_milliseconds_count[1m])` stays non-zero |
| 5 | Bad retrieval (irrelevant docs) | Retrieval | Prevent poor answers | Retrieval Similarity p50 drops | Manual → Retrieval Similarity (p50/p95) | `histogram_quantile(0.50, sum(rate(rag_retrieve_similarity_score_bucket[1m])) by (le))` dropping |
| 6 | Empty retrievals | Retrieval | Detect missing/bad ingestion | `rag_retrieve_empty_total` rate > 0 | Manual → Empty Retrieval Rate | `sum(rate(rag_retrieve_empty_total[1m]))` > 0 |
| 7 | Invalid Bifrost virtual key | Provider | Prevent unauthorized access | Alert on 401 from gateway; Gateway Success % drops below 100 | Bifrost → Gateway Success % | `bifrost_success_requests_total` / `bifrost_upstream_requests_total` < 100% |
| 8 | Invalid provider API token | Provider | Detect provider auth failure | Gateway Success % drops; Bifrost traces show provider 401/403 | Bifrost → Gateway Success % + trace explorer | `http.response.status_code=401` on Bifrost spans |
| 9 | Provider timeout or 5xx | Provider | Avoid user-facing errors, trigger failover | Bifrost Upstream Latency spikes + Gateway Success % drops | Bifrost → Upstream Latency + Gateway Success % | `bifrost_upstream_latency_seconds` p50 spikes, success % < 100 |
| 10 | **LLM provider slow** | Provider | Identify provider latency | Both gateway and app latency spike together | Bifrost → Upstream Latency | `bifrost_upstream_latency_seconds` p50 spikes |
| 11 | Gateway connectivity slow | Provider | Identify gateway as bottleneck | App latency spikes but gateway upstream latency is normal | Bifrost → Upstream Latency vs OpenLLMetry → Operation Duration | `gen_ai_client_operation_duration_seconds` high while `bifrost_upstream_latency_seconds` is normal |
| 11 | **Gateway retry storms** | Provider | Detect provider instability causing retries | Bifrost Retries p95 increases or retry sample rate spikes | Bifrost → Bifrost Retries | `bifrost_request_retries` histogram non-zero |
| 12 | Token budget blown | Model | Control costs before bill shock | Bifrost Cost Rate exceeds threshold | Bifrost → Bifrost Cost Rate | `sum(rate(bifrost_cost_USD_total[1m]))` > budget |
| 13 | **Provider cost runaway** | Model | Catch runaway loops or expensive models | Bifrost Tokens rate growing faster than Upstream Requests rate | Bifrost → Bifrost Tokens vs Bifrost Upstream Requests | `sum(rate(bifrost_input_tokens_total[1m])) / sum(rate(bifrost_upstream_requests_total[1m]))` |
| 14 | Wrong/blocked model name | Model | Prevent silent routing failures | Gateway Success % drops; trace shows `model_blocked` | Bifrost → Gateway Success % + trace explorer | `sum(bifrost_success_requests_total) / sum(bifrost_upstream_requests_total) * 100` drops; trace span error |
| 15 | Model selection driving cost | Model | Identify which model is most expensive | Bifrost Cost Rate by model shows outlier | Bifrost → Bifrost Cost Rate | `sum(rate(bifrost_cost_USD_total[1m])) by (model)` — compare across models |
| 16 | Token-heavy prompts (RAG context too large) | Model | Optimize cost by reducing context | OpenLLMetry Token Usage Distribution p95 shows input tokens growing | OpenLLMetry → Token Usage Distribution | `histogram_quantile(0.95, sum(rate(gen_ai_client_token_usage_bucket[1m])) by (le))` |
| 17 | Per-user abuse | User | Identify who is overusing | Filter traces by `user.id`; token rate per user | Trace explorer | `user.id` on `rag.ask` spans — correlate with Bifrost token metrics |
| | **Not detectable** | | | | | |
| 18 | Bad chunking | Retrieval | — | — | — | Similarity scores may look fine but chunks may be wrong granularity |
| 19 | Model degradation | Model | — | — | — | Gateway sees tokens and latency, not correctness |
| 20 | Hallucination | Model | — | — | — | Needs eval or human review |
