# AI Observability

A minimal FastAPI RAG application for benchmarking AI observability tools. Same app, different instrumentation per experiment, compare what each tool captures.

## Structure

```
├── base/                          # Uninstrumented RAG app (source of truth)
│   ├── app.py                     # FastAPI routes: /health, /ingest, /ask
│   ├── rag.py                     # RAG pipeline: chunk, embed, store, retrieve, generate
│   ├── pyproject.toml
│   ├── .env.example
│   ├── Makefile
│   └── sample_data/
│
├── infra/                         # Shared infrastructure (pgvector + SigNoz)
│   ├── docker-compose.yml         # pgvector
│   ├── bootstrap_signoz.sh        # Clones and runs SigNoz
│   ├── Makefile                   # make up / make down / make check-signoz-*
│   └── README.md
│
├── experiments/
│   ├── 01_otel/                   # Vanilla OpenTelemetry (manual spans, metrics, logs)
│   └── 02_openllmetry/            # Traceloop/OpenLLMetry (auto-instruments OpenAI SDK)
│
├── pyproject.toml                 # Repo-level tooling (ruff, pyright)
└── .gitignore
```

## Quick start

```bash
# 1. Start infra (terminal 1)
cd infra
make up
# Wait ~60s, open http://localhost:3301, sign up (first time only)

# 2. Run an experiment (terminal 2)
cd experiments/02_openllmetry
cp .env.example .env   # fill in API keys
make app

# 3. Test (terminal 3)
cd experiments/02_openllmetry
make ingest
make ask

# 4. View traces/logs/metrics at http://localhost:3301
```

## Experiments

| # | Name | What it demonstrates |
|---|------|---------------------|
| 01 | `01_otel` | Vanilla OTel: manual spans, metrics, logs. Shows baseline effort. |
| 02 | `02_openllmetry` | Traceloop auto-instruments OpenAI SDK. Token counts, model info, prompts captured for free. |

## Observable surfaces

| Layer | What's observable |
|-------|------------------|
| HTTP/API | Request latency, status codes, route-level metrics |
| RAG/Vector DB | Embedding calls, pgvector query latency (with manual spans) |
| LLM | Token usage, model, prompt/completion content, generation latency |
