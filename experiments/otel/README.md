# otel — Vanilla OpenTelemetry

Instruments the RAG app with plain OpenTelemetry — manual spans, metrics, and logs. No LLM-specific auto-instrumentation.

## Prerequisites

- **Docker and Docker Compose.** The app runs in a container; `make build` then `make up`.
- **Shared infra up first:** `cd ../../infra && make up`.
  - Brings up pgvector, the OTel collector gateway (OTLP on `host.docker.internal:4418`), and the selected sink.
  - For `make dashboard` to land, use a metrics-capable sink: `SINK=grafana`.
- **`.env`** copied from `.env.example`, no hidden defaults:
  - `EMBED_API_KEY` — API key for the embedding endpoint. e.g. `EMBED_API_KEY=your-embed-api-key`
  - `EMBED_BASE_URL` — base URL of the embedding provider. e.g. `EMBED_BASE_URL=https://openrouter.ai/api/v1`
  - `EMBED_MODEL` — embedding model name. e.g. `EMBED_MODEL=openai/text-embedding-3-small`
  - `EMBED_DIM` — embedding vector dimension. e.g. `EMBED_DIM=1536`
  - `CHAT_API_KEY` — API key for the chat endpoint (OpenRouter, direct). e.g. `CHAT_API_KEY=your-openrouter-api-key`
  - `CHAT_BASE_URL` — base URL of the chat provider (OpenRouter, direct, no gateway yet). e.g. `CHAT_BASE_URL=https://openrouter.ai/api/v1`
  - `CHAT_MODEL` — chat model name. e.g. `CHAT_MODEL=deepseek/deepseek-v4.1-flash`
  - `DATABASE_URL` — pgvector Postgres connection string. e.g. `DATABASE_URL=postgresql://rag:rag@host.docker.internal:5432/rag`
  - `OTEL_SERVICE_NAME` — service name on emitted telemetry. e.g. `OTEL_SERVICE_NAME=ai-obs-otel`
  - `OTEL_EXPORTER_OTLP_ENDPOINT` — OTLP target; the app sends to the gateway, never a sink directly. e.g. `OTEL_EXPORTER_OTLP_ENDPOINT=http://host.docker.internal:4418`
- **`python3` on the host** for the `make ingest` / `make ask` / `make dashboard` targets.

## Usage

```bash
# 1. Start shared infra
cd ../../infra && make up

# 2. Configure
cp .env.example .env
# Edit .env with your keys

# 3. Build and run
make build
make up

# 4. Load the Grafana dashboard (after infra's grafana sink is up)
make dashboard

# 5. Test (from another terminal)
make ingest
make ask

# 6. View in Grafana at http://localhost:3000 (admin/admin)
#    Explore -> Tempo -> service.name = ai-obs-otel  (traces)
#    Explore -> Prometheus -> http_server_duration_milliseconds_count  (metrics)
#    Dashboards -> the imported dashboard is ready to use
```

## Flow

```mermaid
graph LR
    User -->|POST /ask| FastAPI
    FastAPI -->|span: rag.ask| RAG
    RAG -->|span: rag.embed| OpenAI[OpenAI Embeddings]
    RAG -->|span: rag.vector_search| PG[pgvector]
    RAG -->|span: rag.generate| LLM[Chat Completions]
    FastAPI -->|OTLP :4418| Gateway[OTel Collector Gateway]
    Gateway -->|OTLP| Sink[Sink]
```

## Example traces

### POST /ask (3.08s, 9 spans)

![Trace: POST /ask](images/trace-ask.png)

```
POST /ask (3.08s)
├── POST /ask http receive (16µs)
├── rag.ask (3.07s)
│   ├── rag.retrieve (659ms)
│   │   ├── rag.embed (642ms)
│   │   └── rag.vector_search (12ms)
│   └── rag.generate (2.39s)
├── POST /ask http send (42µs)
└── POST /ask http send (21µs)
```

| # | Span | Parent | Duration | Source | What it tells you | Sample attributes |
|---|------|--------|----------|--------|-------------------|-------------------|
| 1 | `POST /ask` | — | 3.08s | FastAPI auto | How long did the user wait? | `http.method=POST`, `http.target=/ask`, `http.status_code=200` |
| 2 | `POST /ask http receive` | `POST /ask` | 16µs | FastAPI auto | How long to receive the request? | — |
| 3 | `rag.ask` | `POST /ask` | 3.07s | Manual | How long did the full RAG pipeline take? | — |
| 4 | `rag.retrieve` | `rag.ask` | 659ms | Manual | How long did retrieval take? | `retrieve.top_k=5` |
| 5 | `rag.embed` | `rag.retrieve` | 642ms | Manual | How long did query embedding take? | `embed.model=openai/text-embedding-3-small`, `embed.num_texts=1` |
| 6 | `rag.vector_search` | `rag.retrieve` | 12ms | Manual | Is the database the bottleneck? | — |
| 7 | `rag.generate` | `rag.ask` | 2.39s | Manual | How long did LLM generation take? | `generate.model=claude-sonnet-4`, `generate.num_context_chunks=5` |
| 8 | `POST /ask http send` (×2) | `POST /ask` | ~42µs | FastAPI auto | How long to send the response? | — |

### POST /ingest (3.38s, 7 spans)

![Trace: POST /ingest](images/trace-ingest.png)

```
POST /ingest (3.38s)
├── POST /ingest http receive (76µs)
├── rag.ingest (3.28s)
│   ├── rag.embed (3.18s)
│   └── rag.store (48ms)
├── POST /ingest http send (120µs)
└── POST /ingest http send (12µs)
```

| # | Span | Parent | Duration | Source | What it tells you | Sample attributes |
|---|------|--------|----------|--------|-------------------|-------------------|
| 1 | `POST /ingest` | — | 3.38s | FastAPI auto | How long did ingestion take? | `http.method=POST`, `http.target=/ingest`, `http.status_code=200` |
| 2 | `POST /ingest http receive` | `POST /ingest` | 76µs | FastAPI auto | How long to receive the upload? | — |
| 3 | `rag.ingest` | `POST /ingest` | 3.28s | Manual | How long did the full ingest pipeline take? | `ingest.source=kubernetes.txt` |
| 4 | `rag.embed` | `rag.ingest` | 3.18s | Manual | How long to embed all chunks? | `embed.model=openai/text-embedding-3-small`, `embed.num_texts=7` |
| 5 | `rag.store` | `rag.ingest` | 48ms | Manual | How long to write to pgvector? | `store.source=kubernetes.txt`, `store.num_chunks=7` |
| 6 | `POST /ingest http send` (×2) | `POST /ingest` | ~120µs | FastAPI auto | How long to send the response? | — |

**What you can see:** Full pipeline structure for both read and write paths. Where time is spent (embedding dominates both).

**What you can't see:** Token counts, model metadata, prompt/completion content — vanilla OTel doesn't know about LLM APIs.

**No LLM-specific metrics.** Token usage, model info, and cost are not captured — vanilla OTel has no concept of `gen_ai.*` semantics.

## Metrics dashboard

![Metrics dashboard](images/metrics-dashboard.png)

### FastAPI — HTTP Metrics (auto-instrumented)

| Panel | Metric | PromQL | What it tells you |
|-------|--------|--------|-------------------|
| Request Rate (req/s) | `http_server_duration_milliseconds_count` | `sum(rate(..._count[1m])) by (http_target)` | Requests per second by endpoint. Shows traffic volume. |
| Request Duration p95 (ms) | `http_server_duration_milliseconds_bucket` | `histogram_quantile(0.95, sum(rate(..._bucket[1m])) by (le, http_target))` | Worst-case latency per endpoint. What the user experiences. |
| Request Duration p50 (ms) | `http_server_duration_milliseconds_bucket` | `histogram_quantile(0.50, ...)` | Typical latency per endpoint. |
| Error Rate (5xx) | `http_server_duration_milliseconds_count` | `sum(rate(..._count{http_status_code=~"5.."}[1m])) by (http_target)` | Rate of server errors. Non-zero = failures reaching users. |
| Active Requests | `http_server_active_requests` | `http_server_active_requests` | Concurrent in-flight requests. High = saturated. |
| Response Size (bytes, avg) | `http_server_response_size_bytes_sum/count` | `sum(rate(..._sum[1m])) / sum(rate(..._count[1m]))` | Average response payload. Large /ask = verbose LLM output. |

## Failure modes

See [failure_modes.md](failure_modes.md).

## Appendix: Metric Dimensions

### `http.server.duration` / `http.server.request.size` / `http.server.response.size`

| Dimension | Example | Purpose |
|-----------|---------|---------|
| `http.method` | `POST` | Slice by HTTP method |
| `http.target` | `/ask` | Slice by endpoint path |
| `http.status_code` | `200`, `500` | Error rate = filter by 5xx |
| `http.flavor` | `1.1` | HTTP version |
| `net.host.port` | `8001` | Port |

### `http.server.active_requests`

| Dimension | Example | Purpose |
|-----------|---------|---------|
| `http.method` | `POST` | Slice by method |
| `http.scheme` | `http` | Protocol |
