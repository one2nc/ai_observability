# Shared Infrastructure

Centralized services used by all experiments.

## Services

| Service | Port | Purpose |
|---------|------|---------|
| Postgres + pgvector | 5432 | Vector store for RAG |
| SigNoz UI | 3301 | Observability UI (traces, metrics, logs) |
| SigNoz OTLP (gRPC) | 4317 | Telemetry ingestion |
| SigNoz OTLP (HTTP) | 4318 | Telemetry ingestion |

## Usage

```bash
make up       # start all infra (foreground)
make down     # stop
make clean    # stop + remove all volumes (full reset)
```

## First-run setup (required once)

After `make up`, SigNoz's OTLP collector will NOT accept data until you create an admin account:

1. Wait for all containers to be healthy (~60s)
2. Open http://localhost:3301
3. Create an admin account (any email/password — it's local only)
4. The OTLP collector starts accepting data immediately after signup

This only needs to happen once. The account persists across `make down` / `make up` cycles.
If you run `make clean`, you'll need to sign up again.

## Verify data is flowing

```bash
make check-signoz-traces
make check-signoz-logs
make check-signoz-metrics
```
