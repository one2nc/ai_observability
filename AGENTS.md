# AGENTS.md

## Project Goal

Benchmark AI observability by instrumenting applications with different OTel-based setups. Each experiment answers: "what can I see, what can't I see, and what failure modes can I catch?"

The output is a comparison matrix showing the tradeoffs between auto-instrumentation, manual instrumentation, and AI gateways — grounded in real traces, metrics, and logs.

## Project Structure

```
base/                              # Uninstrumented RAG app (reference)
infra/                             # Shared infrastructure
├── postgres/                      # pgvector
├── otel-collector-gateway/        # Generic OTel collector (apps send here)
├── sinks/                         # Backends (signoz, grafana, langfuse, etc.)
│   ├── signoz/
│   ├── grafana/
│   └── langfuse/                  # LLM eval backend; traces only, no metrics
└── .vendor/                       # Cloned repos (gitignored)

experiments/
├── otel/                          # Vanilla OTel manual spans
├── openllmetry/                   # Traceloop auto-instrumentation
├── openllmetry_manual/            # Auto + manual spans + custom metrics
├── bifrost/                       # Bifrost AI gateway telemetry
├── langfuse_introduction/         # Langfuse feature tour (orientation)
├── langfuse_openai_agents/        # Langfuse-only observability for the agent
└── ...                            # Add more experiments here
```

## Experiment Structure

Each experiment is standalone and self-contained. Language, framework, and internal file layout are up to the experiment. The contract is the interface:

### Required files

- `docker-compose.yml` — App container(s)
- `Dockerfile` — Build instructions
- `.env.example` — Required env vars (no defaults for critical config)
- `Makefile` — Must provide at minimum: `make up`, `make down`, `make ask`
- `README.md` — Must include:
  - Flow diagram (mermaid)
  - Example traces with span breakdown table (columns: #, Span, Parent, Duration, Source, What it tells you, Sample attributes)
  - Span attributes (auto + manual) with examples
  - Metrics dashboard section with per-panel table (columns: Panel, Metric, PromQL, What it tells you)
  - Metric dimensions appendix (list all dimensions per metric with examples)
  - Failure modes table (columns: #, Failure mode, Why?, How?, Where?, What?)
  - Usage instructions
- Dashboard JSON — Importable dashboard for the configured sink. Every metric documented in the README must have a corresponding panel.
  - Exception: an experiment whose backend has no metrics store (e.g. `langfuse_*`) ships no dashboard. It must say so explicitly in the Metrics dashboard section and explain what replaces it.

### Internal structure

Up to the experiment. Python with FastAPI, Go with net/http, a shell script — whatever demonstrates the instrumentation clearly.

## Key Principles

1. **Apps don't know about sinks.** Every experiment sends OTLP to `host.docker.internal:4418` (the gateway). The gateway routes to whatever sink is configured.
   - Documented exception: the `langfuse_*` experiments export directly to Langfuse, because prompt management, scores and datasets are Langfuse API features with no OTel equivalent. The coupling is the point being measured, not an oversight. Traces alone can still be routed through the gateway with `SINK=langfuse`.

2. **Sinks are swappable.** Add a new sink in `infra/sinks/<name>/`. Update the gateway config. No app changes.

3. **Each experiment is shareable standalone.** You can zip up any experiment folder and hand it to someone without them needing the rest of the repo.

4. **Fail fast on missing config.** All required env vars must be checked at startup. No hidden defaults.

## Adding a New Experiment

1. Create `experiments/<name>/`
2. Implement the application with instrumentation
3. Add `Dockerfile`, `docker-compose.yml`, `.env.example`, `Makefile`
4. Write `README.md` following the structure above
5. Create a dashboard JSON with panels for all documented metrics
6. Test: `make up`, `make ask`, verify data in sink

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
8. **Visualize metrics, don't just list them.** Create importable dashboards for the configured sink. Every metric documented in the README must have a corresponding dashboard panel.
