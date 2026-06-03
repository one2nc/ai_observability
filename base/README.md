# base — Uninstrumented RAG App

The source of truth. A minimal FastAPI RAG application with zero observability instrumentation.

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/ingest` | POST | Upload a file, chunk + embed + store in pgvector |
| `/ask` | POST | Question → retrieve → LLM summarize |

## Stack

- **FastAPI** — HTTP API
- **OpenAI SDK** — embeddings (OpenRouter) + chat completions (Bifrost gateway)
- **pgvector** — vector storage and cosine similarity search

## Usage

```bash
cd base
cp .env.example .env   # fill in API keys
make setup             # uv sync
make infra             # start postgres (via infra/)
make app               # run locally on :8001
make ingest            # upload sample_data/kubernetes.txt
make ask               # ask a question
```

## No observability

This app has no traces, metrics, or logs export. It exists as the baseline that experiments copy and instrument.
