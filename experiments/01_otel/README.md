# 01_otel — Vanilla OpenTelemetry

Instruments the RAG app with plain OpenTelemetry (no LLM-specific tooling).

## Flow

```mermaid
graph LR
    User -->|POST /ask| FastAPI
    FastAPI -->|span: rag.ask| RAG
    RAG -->|span: rag.embed| OpenAI[OpenAI Embeddings]
    RAG -->|span: rag.vector_search| PG[pgvector]
    RAG -->|span: rag.generate| LLM[Chat Completions]
    FastAPI -->|OTLP| Collector[SigNoz OTel Collector]
    Collector --> ClickHouse
    ClickHouse --> SigNoz[SigNoz UI]
```

## What this captures

| What | How | Visible in SigNoz? |
|------|-----|-------------------|
| HTTP request spans | FastAPI auto-instrumentation | Yes |
| `rag.embed` span | Manual span with model + num_texts | Yes |
| `rag.vector_search` span | Manual span | Yes |
| `rag.generate` span | Manual span with model + num_chunks | Yes |
| `rag.ingest` / `rag.ask` spans | Manual parent spans | Yes |
| LLM token usage | Not captured (vanilla OTel doesn't know about LLM APIs) | No |
| Embedding token usage | Not captured | No |

## What this does NOT capture (gaps)

- Token counts (input/output/total)
- Model response metadata
- Prompt/completion content
- Cost estimation

These gaps are what `02_openllmetry` fills.

## Usage

```bash
# 1. Start shared infra (from repo root)
make -C ../../infra up

# 2. Setup deps
make setup

# 3. Configure
cp .env.example .env
# Edit .env with your keys

# 4. Run
make app

# 5. Test
make ingest
make ask

# 6. View traces
# Open http://localhost:8080 (SigNoz UI)
```
