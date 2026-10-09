# base: Uninstrumented RAG App

The source of truth. A minimal FastAPI RAG application with zero observability instrumentation.

## RAG primer

RAG = Retrieval-Augmented Generation.

- The LLM does not answer from memory alone. It answers from documents you supply.
- Two phases:
  - **Ingest** (once per document): split text into chunks, turn each chunk into an embedding (a vector), store the vectors in a database.
  - **Ask** (per question): embed the question, find the chunks whose vectors are most similar, hand those chunks to the LLM as context, return its answer.
- An **embedding** is a numeric vector representing meaning. Similar text → nearby vectors.
- **Retrieval** uses cosine similarity in pgvector to pick the top-k closest chunks.
- The LLM is told to answer **only** from the retrieved context, so it stays grounded in your data instead of guessing.
- Why it matters here: each step (embed, vector search, generate) is a place to observe latency, cost, and quality, which is what the later experiments instrument.

### Ingest: user sends data

```mermaid
sequenceDiagram
    participant U as User
    participant API as FastAPI /ingest
    participant E as Embedding model
    participant DB as pgvector

    U->>API: POST /ingest (upload file)
    API->>API: chunk text into pieces
    API->>E: embed each chunk
    E-->>API: vectors
    API->>DB: store chunks + vectors
    DB-->>API: stored count
    API-->>U: { "chunks": N }
```

### Ask: user asks a question

```mermaid
sequenceDiagram
    participant U as User
    participant API as FastAPI /ask
    participant E as Embedding model
    participant DB as pgvector
    participant LLM as Chat model

    U->>API: POST /ask (query)
    API->>E: embed the query
    E-->>API: query vector
    API->>DB: top-k similar chunks (cosine)
    DB-->>API: matching chunks
    API->>LLM: query + retrieved context
    LLM-->>API: grounded answer
    API-->>U: { "answer": ..., "sources": [...] }
```

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/ingest` | POST | Upload a file, chunk + embed + store in pgvector |
| `/ask` | POST | Question → retrieve → LLM summarize |

## Stack

- **FastAPI**: HTTP API
- **OpenAI SDK**: embeddings and chat completions (both via OpenRouter, direct, no gateway yet)
- **pgvector**: vector storage and cosine similarity search

## Prerequisites

- **Runs on the host, not in Docker.** This is the only phase that does; the experiments are Dockerized.
  - `uv` installed (the app runs via `uv run python app.py`). e.g. `pip3 install uv`
  - `make setup` runs `uv sync` to create the virtualenv.
- **Shared infra for Postgres + pgvector.**
  - Docker and Docker Compose (infra runs in containers).
  - `make infra` starts it via `infra/`.
- **`.env`** copied from `.env.example`, with no hidden defaults:
  - `EMBED_API_KEY`: API key for the embedding endpoint (OpenRouter, direct). e.g. `EMBED_API_KEY=your-openrouter-api-key`
  - `EMBED_BASE_URL`: base URL of the embedding provider. e.g. `EMBED_BASE_URL=https://openrouter.ai/api/v1`
  - `EMBED_MODEL`: embedding model name. e.g. `EMBED_MODEL=openai/text-embedding-3-small`
  - `EMBED_DIM`: embedding vector dimension. e.g. `EMBED_DIM=1536`
  - `CHAT_API_KEY`: API key for the chat endpoint (OpenRouter, direct, no gateway yet). e.g. `CHAT_API_KEY=your-openrouter-api-key`
  - `CHAT_BASE_URL`: base URL of the chat provider. e.g. `CHAT_BASE_URL=https://openrouter.ai/api/v1`
  - `CHAT_MODEL`: chat model name. e.g. `CHAT_MODEL=openai/gpt-4o-mini`
  - `DATABASE_URL`: pgvector Postgres connection string. e.g. `DATABASE_URL=postgresql://rag:rag@localhost:5432/rag`
- **`python3` on the host** for the `make ingest` / `make ask` targets (they pipe curl through `python3 -m json.tool`).

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
