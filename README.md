# AI Observability

A minimal FastAPI RAG application for benchmarking AI observability tools.

## Structure

```
├── base/                  # Uninstrumented RAG app (source of truth)
│   ├── app.py             # FastAPI routes: /health, /ingest, /ask
│   ├── rag.py             # RAG pipeline: chunk, embed, store, retrieve, generate
│   ├── requirements.txt   # App-only dependencies
│   ├── docker-compose.yml # Postgres + pgvector
│   ├── Makefile
│   ├── .env.example
│   └── sample_data/
│       └── kubernetes.txt
│
├── experiments/           # Per-tool instrumentation (each is a standalone copy of base)
│   └── (coming soon)
│
├── pyproject.toml         # Repo-level tooling (ruff, pyright)
└── .gitignore
```

## Quick start (base app)

```bash
cd base
cp .env.example .env       # add your OPENAI_API_KEY
make setup                 # pip install -r requirements.txt
make infra                 # docker compose up (postgres+pgvector)
make run                   # start FastAPI on :8000
make ingest                # upload sample_data/kubernetes.txt
make ask                   # ask "What does the kube-scheduler do?"
```

## Observable surfaces

| Layer | What's observable |
|-------|------------------|
| HTTP/API | Request latency, status codes, route-level metrics |
| RAG/Vector DB | Embedding calls, pgvector query latency, relevance scores |
| LLM | Token usage, model, prompt/completion content, generation latency |
