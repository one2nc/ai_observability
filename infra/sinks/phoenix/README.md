# Phoenix sink

Self-hosted Arize Phoenix as a trace sink for AI observability experiments.
Phoenix is useful when the question is about LLM span inspection, OpenInference
attributes and trace-level troubleshooting rather than general metrics/log
dashboards.

## What it does and does not accept

| Signal | Supported? | Where it goes |
|--------|-----------|---------------|
| Traces | Yes | Phoenix OTLP HTTP collector at `POST /v1/traces` |
| Metrics | No app metrics store | Gateway keeps OTLP metrics on `:8889` for Prometheus-compatible scraping |
| Logs | No | Gateway stdout only |

Phoenix exposes its UI and OTLP HTTP trace collector on port `6006`, and its
OTLP gRPC trace collector on port `4317` inside the container. This repo maps
gRPC to host port `14317` to avoid colliding with the gateway's public OTLP gRPC
port.

Data persists across normal infra restarts. `PHOENIX_WORKING_DIR` is set to
`/mnt/data`, and the Compose stack stores Phoenix state in the named Docker
volume `phoenix_phoenix-data`, so traces, admin password changes, secrets and
custom provider settings survive:

```bash
make down SINK=phoenix
make up SINK=phoenix
```

Only `make clean SINK=phoenix` removes that volume.

## Usage

```bash
make up SINK=phoenix
```

Open http://localhost:6006 and sign in as the default local admin:

```text
email: admin@localhost
password: admin
```

`PHOENIX_DEFAULT_ADMIN_INITIAL_PASSWORD` controls this initial password. Phoenix
only reads it when the default admin account is first created; if you already
started Phoenix with the same volume, change the password in the UI or recreate
the Phoenix volume for a clean local instance.

Experiments still send OTLP to the repo gateway:

```text
OTEL_EXPORTER_OTLP_ENDPOINT=http://host.docker.internal:4418
```

The gateway uses `otel-collector-gateway/config.phoenix.yaml`:

| Signal | Gateway exporter | Backend |
|--------|------------------|---------|
| Traces | `otlphttp/phoenix` | Phoenix `${PHOENIX_OTLP_ENDPOINT}/v1/traces` with `Authorization: Bearer ${PHOENIX_ADMIN_SECRET}` |
| Metrics | `prometheus` | Exposed at gateway `:8889`; Phoenix stores none |
| Logs | `debug` | Collector stdout only |

Authentication is enabled by default for this sink because Phoenix Settings
features such as Secrets and Custom AI Providers require an admin user. The
local `.env` must provide:

```text
PHOENIX_ENABLE_AUTH=true
PHOENIX_SECRET=...
PHOENIX_ADMIN_SECRET=...
PHOENIX_DEFAULT_ADMIN_INITIAL_PASSWORD=admin
```

`PHOENIX_ADMIN_SECRET` lets the gateway keep sending OTLP traces after auth is
enabled. In a shared environment, rotate all three values and create a normal
system API key from the Phoenix UI.

## Verify

```bash
make check-phoenix
```

This checks Phoenix's `/healthz` endpoint and confirms the REST API is
reachable with the configured admin secret.

## Custom AI providers

Sign in as an admin, then use Settings to add the provider credentials/secrets
needed by Phoenix. The experiment app itself still calls its configured
OpenAI-compatible endpoint directly; Phoenix's custom providers are for Phoenix
features such as Playground and prompt tooling, not for routing experiment app
traffic.

## Experiment fit

Use `SINK=phoenix` for experiments that compare:

- Whether spans follow OpenInference conventions.
- How well LLM inputs, outputs, token usage and tool calls appear in traces.
- What Phoenix can inspect from generic OTLP versus Phoenix/OpenInference-aware
  instrumentation.

Use `SINK=grafana` or `SINK=signoz` when the experiment needs metric dashboards
or searchable logs.
