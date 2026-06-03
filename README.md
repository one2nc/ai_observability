# AI Observability

Benchmarking AI observability using a minimal RAG application. Same app, different instrumentation per experiment — compare what each approach captures.

## Experiments

| # | Experiment | What it demonstrates | README |
|---|------------|---------------------|--------|
| — | `base/` | Uninstrumented RAG app (source of truth) | [README](base/README.md) |
| 01 | `experiments/01_otel` | Vanilla OTel: manual spans, metrics, logs | [README](experiments/01_otel/README.md) |
| 02 | `experiments/02_openllmetry` | OpenLLMetry auto-instruments OpenAI SDK (tokens, model, prompts for free) | [README](experiments/02_openllmetry/README.md) |
| 03 | `experiments/03_openllmetry_manual` | OpenLLMetry + manual spans (retrieval quality, per-user attribution) | [README](experiments/03_openllmetry_manual/README.md) |

## Infrastructure

Shared infra (pgvector, OTel collector gateway, sinks) lives in [`infra/`](infra/README.md).

## Observable surfaces

| Layer | What's observable |
|-------|------------------|
| HTTP/API | Request latency, status codes, route-level metrics |
| RAG/Vector DB | Embedding calls, pgvector query latency, retrieval similarity scores |
| LLM | Token usage, model, prompt/completion content, generation latency |
