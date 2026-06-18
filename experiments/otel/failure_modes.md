# Failure Modes — otel

| # | Failure mode | Layer | Why? | How? | Where? | What? |
|---|---|---|---|---|---|---|
| 1 | **App is slow** | Application | Identify which RAG step is the bottleneck | Check which span is longest in trace | Trace explorer | `rag.embed` / `rag.generate` span durations |
| 2 | **Database down** | Application | Avoid silent retrieval failures | `rag.vector_search` span errors | Trace explorer | `rag.vector_search` span with error status |
| 3 | High request latency | Application | SLA monitoring | Alert on p95 exceeding threshold | FastAPI → Request Duration p95 | `http.server.duration` metric |
| 4 | App errors (5xx) | Application | Detect crashes, unhandled exceptions | Alert when 5xx rate > 0 | FastAPI → Error Rate (5xx) | `http.server.duration{http_status_code=~"5.."}` |
| 5 | App saturation | Application | Prevent request queuing, scale up | Alert when active requests stays high | FastAPI → Active Requests | `http.server.active_requests` |
| 6 | Embedding API down | Provider | Detect upstream failures | `rag.embed` span errors | Trace explorer | `rag.embed` span with error status |
| | **Not detectable** | | | | | |
| 7 | Bad retrieval quality | Retrieval | — | — | — | No similarity scores |
| 8 | LLM provider slow vs app slow | Provider | — | — | — | No `openai.chat` span to isolate LLM time |
| 9 | Token budget blown | Model | — | — | — | No token metrics |
| 10 | Cost runaway | Model | — | — | — | No token/cost metrics |
| 11 | Per-user abuse | User | — | — | — | No `user.id` |
