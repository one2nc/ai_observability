# AGENTS.md

## Project Goal

Benchmark AI observability by instrumenting a minimal RAG application with different OTel-based setups. Each experiment answers: "what can I see, what can't I see, and what failure modes can I catch?"

The output is a comparison matrix showing the tradeoffs between auto-instrumentation, manual instrumentation, and AI gateways — grounded in real traces, metrics, and logs.

## Project Structure

```
base/                              # Uninstrumented RAG app (source of truth)
infra/                             # Shared infrastructure
├── postgres/                      # pgvector
├── otel-collector-gateway/        # Generic OTel collector (apps send here)
├── sinks/                         # Backends (signoz, victoriametrics, etc.)
│   └── signoz/
└── .vendor/                       # Cloned repos (gitignored)

experiments/
├── 01_otel/                       # Vanilla OTel manual spans
├── 02_openllmetry/                # Traceloop auto-instrumentation
├── 03_openllmetry_manual/         # Auto + manual spans + custom metrics
└── ...                            # Add more experiments here
```

## Experiment Structure

Each experiment is a standalone, self-contained copy of the base app with instrumentation added. It must have:

- `app.py` — FastAPI app with instrumentation wired in
- `rag.py` — RAG pipeline (may have manual spans)
- `instrument.py` — Swappable instrumentation setup
- `docker-compose.yml` — App container
- `Dockerfile`
- `pyproject.toml` — Dependencies
- `.env.example` — Required env vars (no defaults for critical config)
- `Makefile` — `make up`, `make down`, `make ingest`, `make ask`
- `README.md` — Must include:
  - Flow diagram (mermaid)
  - Example trace with span breakdown table
  - Span attributes (auto + manual)
  - Metrics exposed with dimensions
  - Metric dimensions appendix (list all dimensions per metric with examples)
  - Failure modes table (what's detectable, what's not)
  - Usage instructions
- `dashboard.json` (optional) — Pre-built dashboard for the configured sink

## Key Principles

1. **Apps don't know about sinks.** Every experiment sends OTLP to `host.docker.internal:4418` (the gateway). The gateway routes to whatever sink is configured.

2. **Sinks are swappable.** Add a new sink in `infra/sinks/<name>/`. Update the gateway config. No app changes.

3. **Each experiment is shareable standalone.** You can zip up any experiment folder and hand it to someone without them needing the rest of the repo.

4. **Fail fast on missing config.** All required env vars must be checked at startup. No hidden defaults.

5. **Idempotent ingestion.** Re-ingesting the same file replaces existing chunks.

## Adding a New Experiment

1. Copy `base/` to `experiments/<name>/`
2. Add `instrument.py` with the new tool's setup
3. Wire it into `app.py`
4. Add manual spans to `rag.py` if needed
5. Update `pyproject.toml` with new deps
6. Write `README.md` following the structure above
7. Test: `make up`, `make ingest`, `make ask`, verify data in sink

## Adding a New Sink

1. Create `infra/sinks/<name>/docker-compose.yml`
2. Update `infra/otel-collector-gateway/config.yaml` exporters
3. Update `infra/Makefile` with `ifeq ($(SINK),<name>)` blocks
4. Document in `infra/README.md`

## Goals Per Experiment

Each experiment should answer:
- What traces/metrics/logs are emitted?
- What failure modes can be detected?
- What's the effort required (zero-code vs manual)?
- What's NOT visible (gaps)?
- What personas benefit from this setup?

## Development Rules

1. **Test before committing.** All setups must be verified working (app starts, traces/metrics/logs arrive in sink) before any commit.
2. **No git commits without user approval.** Stage changes, show status, wait for explicit go-ahead.
3. **Dockerized by default.** Always prefer containerized setups to prevent "works on my machine" issues. Apps run in Docker, infra runs in Docker.
4. **No hidden defaults for critical config.** Env vars must be explicitly set — fail fast if missing.
5. **No `-d` (detached mode)** for app containers or infra `make up`. Logs should stream to console for visibility.
6. **Don't assume sinks.** Apps send to the OTel collector gateway. Never hardcode SigNoz/Jaeger/etc. in app code or env examples.
7. **Keep experiments independent.** Each experiment folder must work standalone without importing from `base/` or other experiments.
8. **Visualize metrics, don't just list them.** Create importable dashboards for the configured sink (e.g. `dashboard.json` for SigNoz, `dashboard.grafana.json` for Grafana). Every metric documented in the README must have a corresponding dashboard panel.

