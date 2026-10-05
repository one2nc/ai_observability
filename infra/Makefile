.PHONY: up down sink-up sink-down ai-gateway-up ai-gateway-down langfuse-up langfuse-down status clean config check-signoz-traces check-signoz-logs check-signoz-metrics check-grafana check-bifrost check-langfuse langfuse-keys

INFRA_CONFIG ?= .env

include $(INFRA_CONFIG)

SINK ?= signoz
AI_GATEWAY ?= none
SIGNOZ_COMPOSE_DIR := .vendor/signoz/deploy/docker
SIGNOZ_OVERRIDE := sinks/signoz/docker-compose.yml
GRAFANA_COMPOSE_DIR := sinks/grafana
LANGFUSE_COMPOSE_DIR := sinks/langfuse
OTEL_GATEWAY_CONFIG := config.$(SINK).yaml
BIFROST_COMPOSE_DIR := bifrost

SUPPORTED_SINKS := signoz grafana langfuse
SUPPORTED_AI_GATEWAYS := none bifrost

# Langfuse credentials. These defaults match the LANGFUSE_INIT_* headless
# bootstrap in sinks/langfuse/docker-compose.yml, so a fresh stack comes up
# with working keys and no UI signup. Override in .env for anything shared.
LANGFUSE_PORT ?= 3000
LANGFUSE_PUBLIC_KEY ?= pk-lf-11111111-1111-4111-8111-111111111111
LANGFUSE_SECRET_KEY ?= sk-lf-22222222-2222-4222-8222-222222222222
LANGFUSE_HOST ?= http://localhost:$(LANGFUSE_PORT)

# Langfuse's OTLP endpoint wants HTTP Basic base64(public_key:secret_key).
# tr -d '\n' because GNU base64 wraps at 76 columns and this input is longer.
LANGFUSE_OTLP_ENDPOINT ?= http://host.docker.internal:$(LANGFUSE_PORT)/api/public/otel
LANGFUSE_OTLP_AUTH := $(shell printf '%s:%s' '$(LANGFUSE_PUBLIC_KEY)' '$(LANGFUSE_SECRET_KEY)' | base64 | tr -d '\n')

ifneq ($(filter $(SINK),$(SUPPORTED_SINKS)),$(SINK))
$(error Unsupported SINK=$(SINK). Supported values: $(SUPPORTED_SINKS))
endif

ifneq ($(filter $(AI_GATEWAY),$(SUPPORTED_AI_GATEWAYS)),$(AI_GATEWAY))
$(error Unsupported AI_GATEWAY=$(AI_GATEWAY). Supported values: $(SUPPORTED_AI_GATEWAYS))
endif

export BIFROST_PROVIDER
export BIFROST_API_KEY
export BIFROST_PORT
export OTEL_EXPORTER_OTLP_ENDPOINT
export OTEL_EXPORTER_OTLP_TRACES_ENDPOINT
export OTEL_EXPORTER_OTLP_METRICS_ENDPOINT
export LANGFUSE_PORT
export LANGFUSE_PUBLIC_KEY
export LANGFUSE_SECRET_KEY
export LANGFUSE_OTLP_ENDPOINT
export LANGFUSE_OTLP_AUTH

up: ai-gateway-up sink-up
	cd postgres && docker compose up -d
	cd otel-collector-gateway && OTEL_GATEWAY_CONFIG=$(OTEL_GATEWAY_CONFIG) docker compose up -d 

down:
	cd otel-collector-gateway && docker compose down
	cd postgres && docker compose down
	$(MAKE) sink-down
	$(MAKE) ai-gateway-down

ai-gateway-up:
ifeq ($(AI_GATEWAY),bifrost)
	cd $(BIFROST_COMPOSE_DIR) && ./up.sh
endif

ai-gateway-down:
ifeq ($(AI_GATEWAY),bifrost)
	cd $(BIFROST_COMPOSE_DIR) && docker compose down
endif

sink-up:
ifeq ($(SINK),signoz)
	cd sinks/signoz && ./bootstrap.sh
	cd $(SIGNOZ_COMPOSE_DIR) && docker compose -f docker-compose.yaml -f ../../../../$(SIGNOZ_OVERRIDE) up -d
endif
ifeq ($(SINK),grafana)
	cd $(GRAFANA_COMPOSE_DIR) && docker compose up -d
endif
ifeq ($(SINK),langfuse)
	$(MAKE) langfuse-up
endif

sink-down:
ifeq ($(SINK),signoz)
	cd $(SIGNOZ_COMPOSE_DIR) && docker compose -f docker-compose.yaml -f ../../../../$(SIGNOZ_OVERRIDE) down
endif
ifeq ($(SINK),grafana)
	cd $(GRAFANA_COMPOSE_DIR) && docker compose down
endif
ifeq ($(SINK),langfuse)
	$(MAKE) langfuse-down
endif

# Langfuse is also usable *alongside* another sink: the Langfuse SDK talks to
# it directly, so you can keep SINK=grafana for metrics/logs dashboards and
# still have traces, prompts, scores and datasets in Langfuse. These two
# targets exist for exactly that.
langfuse-up:
	cd $(LANGFUSE_COMPOSE_DIR) && docker compose up -d
	@echo "Langfuse UI:  $(LANGFUSE_HOST)"
	@echo "Public key:   $(LANGFUSE_PUBLIC_KEY)"

langfuse-down:
	cd $(LANGFUSE_COMPOSE_DIR) && docker compose down

status:
	cd postgres && docker compose ps
	cd otel-collector-gateway && docker compose ps
ifeq ($(AI_GATEWAY),bifrost)
	cd $(BIFROST_COMPOSE_DIR) && docker compose ps
endif
ifeq ($(SINK),signoz)
	cd $(SIGNOZ_COMPOSE_DIR) && docker compose ps
endif
ifeq ($(SINK),grafana)
	cd $(GRAFANA_COMPOSE_DIR) && docker compose ps
endif
ifeq ($(SINK),langfuse)
	cd $(LANGFUSE_COMPOSE_DIR) && docker compose ps
endif

clean:
	cd otel-collector-gateway && docker compose down -v
	cd postgres && docker compose down -v
ifeq ($(AI_GATEWAY),bifrost)
	cd $(BIFROST_COMPOSE_DIR) && docker compose down -v
endif
ifeq ($(SINK),signoz)
	cd $(SIGNOZ_COMPOSE_DIR) && docker compose -f docker-compose.yaml -f ../../../../$(SIGNOZ_OVERRIDE) down -v
endif
ifeq ($(SINK),grafana)
	cd $(GRAFANA_COMPOSE_DIR) && docker compose down -v
endif
ifeq ($(SINK),langfuse)
	cd $(LANGFUSE_COMPOSE_DIR) && docker compose down -v
endif

check-signoz-traces:
	@docker exec signoz-clickhouse clickhouse-client --query "SELECT count() as total_spans FROM signoz_traces.signoz_index_v3"

check-signoz-logs:
	@docker exec signoz-clickhouse clickhouse-client --query "SELECT count() as total_logs FROM signoz_logs.logs_v2"

check-signoz-metrics:
	@docker exec signoz-clickhouse clickhouse-client --query "SELECT DISTINCT metric_name FROM signoz_metrics.distributed_samples_v4 ORDER BY metric_name"

check-grafana:
	@curl -fsS http://localhost:3000/api/health
	@curl -fsS http://localhost:9091/-/ready
	@curl -fsS http://localhost:3100/loki/api/v1/status/buildinfo
	@curl -fsS http://localhost:3200/api/status/buildinfo

check-bifrost:
	@curl -fsS http://localhost:$${BIFROST_PORT:-8000}/metrics >/dev/null
	@echo "Bifrost metrics endpoint is reachable"

check-langfuse:
	@curl -fsS $(LANGFUSE_HOST)/api/public/health >/dev/null && echo "Langfuse health OK"
	@curl -fsS -u "$(LANGFUSE_PUBLIC_KEY):$(LANGFUSE_SECRET_KEY)" \
		"$(LANGFUSE_HOST)/api/public/traces?limit=1" >/dev/null \
		&& echo "Langfuse API keys accepted"
	@printf 'Traces ingested: '
	@curl -fsS -u "$(LANGFUSE_PUBLIC_KEY):$(LANGFUSE_SECRET_KEY)" \
		"$(LANGFUSE_HOST)/api/public/traces?limit=100" \
		| python3 -c "import json,sys; print(len(json.load(sys.stdin).get('data',[])))"

langfuse-keys:
	@echo "LANGFUSE_HOST=$(LANGFUSE_HOST)"
	@echo "LANGFUSE_PUBLIC_KEY=$(LANGFUSE_PUBLIC_KEY)"
	@echo "LANGFUSE_SECRET_KEY=$(LANGFUSE_SECRET_KEY)"

config:
	@echo "INFRA_CONFIG=$(INFRA_CONFIG)"
	@echo "SINK=$(SINK)"
	@echo "AI_GATEWAY=$(AI_GATEWAY)"
	@echo "BIFROST_PROVIDER=$${BIFROST_PROVIDER:-}"
	@echo "BIFROST_PORT=$${BIFROST_PORT:-8000}"
	@echo "LANGFUSE_HOST=$(LANGFUSE_HOST)"
	@echo "LANGFUSE_OTLP_ENDPOINT=$(LANGFUSE_OTLP_ENDPOINT)"
	@echo "OTEL_EXPORTER_OTLP_ENDPOINT=$${OTEL_EXPORTER_OTLP_ENDPOINT:-http://host.docker.internal:4418}"
	@echo "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=$${OTEL_EXPORTER_OTLP_TRACES_ENDPOINT:-$${OTEL_EXPORTER_OTLP_ENDPOINT:-http://host.docker.internal:4418}/v1/traces}"
	@echo "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT=$${OTEL_EXPORTER_OTLP_METRICS_ENDPOINT:-$${OTEL_EXPORTER_OTLP_ENDPOINT:-http://host.docker.internal:4418}/v1/metrics}"
