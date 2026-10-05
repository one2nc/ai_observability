# Langfuse sink

Self-hosted Langfuse v3 as a sink for this repo. Langfuse is an LLM-specific
observability and evaluation backend rather than a general OTel store, which
makes it different from `signoz` and `grafana` in ways worth knowing before you
pick it.

## What it does and does not accept

| Signal | Supported? | Where it goes |
|--------|-----------|---------------|
| Traces | Yes | `POST /api/public/otel/v1/traces`, HTTP Basic `base64(public_key:secret_key)` |
| Metrics | No | Gateway keeps them on `:8889` for Prometheus to scrape; Langfuse stores none |
| Logs | No | Gateway stdout only |

This is the headline constraint. Langfuse has no metrics store and therefore no
PromQL, so none of the dashboard JSON in `experiments/*/dashboards/` works
against it. What it gives you instead is per-trace LLM detail plus prompt
management, scores, datasets and experiments — things no amount of PromQL
provides.

Because of that split, Langfuse is often most useful running *alongside*
another sink rather than instead of it:

```bash
make up SINK=grafana     # metrics + logs dashboards
make langfuse-up         # traces, prompts, scores, datasets
```

`make langfuse-up` / `make langfuse-down` start and stop this stack
independently of `SINK`.

## Ports

Only the web UI and the MinIO API are published. The upstream Langfuse compose
file publishes Postgres on 5432, MinIO's console on 9091 and the UI on 3000 —
all of which collide with this repo's pgvector, Prometheus and Grafana. Postgres,
ClickHouse, Redis and the worker stay on the internal network.

| Service | Port | Notes |
|---------|------|-------|
| Langfuse UI / API | 3400 | `LANGFUSE_PORT`; upstream default 3000 collides with Grafana |
| MinIO API | 9190 | Needed for media upload presigned URLs |
| MinIO console | 9191 | Loopback only |

## Persistence

Langfuse state persists across normal infra restarts. The Compose stack uses
named Docker volumes for Postgres, ClickHouse, Redis and MinIO:

| Volume | Stores |
|--------|--------|
| `ai-obs-langfuse_langfuse_postgres_data` | Langfuse relational state, projects, users and API keys |
| `ai-obs-langfuse_langfuse_clickhouse_data` | Events, traces and observations |
| `ai-obs-langfuse_langfuse_minio_data` | Event/media blobs |
| `ai-obs-langfuse_langfuse_redis_data` | Redis state |

These survive:

```bash
make langfuse-down
make langfuse-up
```

and also survive `make down SINK=langfuse`. Only `make clean SINK=langfuse` or
manual `docker compose down -v` removes them.

## Credentials

The stack bootstraps itself headlessly via `LANGFUSE_INIT_*`, so the public and
secret keys are known before first boot and experiments can be configured from
`.env` with no clicking:

```bash
make langfuse-keys
```

```text
LANGFUSE_HOST=http://localhost:3400
LANGFUSE_PUBLIC_KEY=pk-lf-11111111-1111-4111-8111-111111111111
LANGFUSE_SECRET_KEY=sk-lf-22222222-2222-4222-8222-222222222222
```

UI login is `local@example.com` / `localpassword`. Override any of these in
`infra/.env` — `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`,
`LANGFUSE_INIT_USER_EMAIL`, `LANGFUSE_INIT_USER_PASSWORD`.

`LANGFUSE_LLM_CONNECTION_WHITELISTED_HOST` defaults to `host.docker.internal`
so Langfuse-hosted LLM-as-a-judge evaluators can call a local OpenAI-compatible
judge model or gateway running on the Docker host. Set it to a comma-separated
list in `infra/.env` if you need additional LLM connection hosts.

`LANGFUSE_INIT_*` only applies on an empty database. If you change the keys
after first boot, either rotate them in the UI or `make langfuse-down` plus
`docker compose down -v` here to start clean.

These are deliberately weak, fixed, local-only credentials for a benchmarking
stack. Don't reuse this compose file anywhere reachable from a network you don't
control.

## Verify

```bash
make check-langfuse
```

Checks `/api/public/health`, confirms the API keys are accepted, and prints how
many traces have been ingested.

## Two ways experiments reach it

| Path | How | Trade-off |
|------|-----|-----------|
| Gateway | App sends OTLP to `:4418`; gateway forwards traces to Langfuse | App stays sink-agnostic per AGENTS.md principle 1, but you get traces only — no prompt linkage, scores or datasets |
| Langfuse SDK | App uses `langfuse` SDK, exports straight to `:3400` | Full Langfuse feature set, but the app is now coupled to one specific backend |

`experiments/langfuse_introduction` and `experiments/langfuse_openai_agents` use the
SDK path, because the features being demonstrated only exist there. Any of the
other seven experiments can use the gateway path with no code change at all —
just `make up SINK=langfuse`.
