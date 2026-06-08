.PHONY: up down sink-up sink-down ai-gateway-up ai-gateway-down status clean config check-signoz-traces check-signoz-logs check-signoz-metrics check-grafana check-bifrost

INFRA_CONFIG ?= .enc
GENERATED_CONFIG := .enc.mk

$(shell ./load-config.sh $(INFRA_CONFIG) > $(GENERATED_CONFIG))
include $(GENERATED_CONFIG)

SINK ?= signoz
AI_GATEWAY ?= none
SIGNOZ_COMPOSE_DIR := .vendor/signoz/deploy/docker
SIGNOZ_OVERRIDE := sinks/signoz/docker-compose.yml
GRAFANA_COMPOSE_DIR := sinks/grafana
OTEL_GATEWAY_CONFIG := config.$(SINK).yaml
BIFROST_COMPOSE_DIR := bifrost

SUPPORTED_SINKS := signoz grafana
SUPPORTED_AI_GATEWAYS := none bifrost

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

sink-down:
ifeq ($(SINK),signoz)
	cd $(SIGNOZ_COMPOSE_DIR) && docker compose -f docker-compose.yaml -f ../../../../$(SIGNOZ_OVERRIDE) down
endif
ifeq ($(SINK),grafana)
	cd $(GRAFANA_COMPOSE_DIR) && docker compose down
endif

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

config:
	@echo "INFRA_CONFIG=$(INFRA_CONFIG)"
	@echo "SINK=$(SINK)"
	@echo "AI_GATEWAY=$(AI_GATEWAY)"
	@echo "BIFROST_PROVIDER=$${BIFROST_PROVIDER:-}"
	@echo "BIFROST_PORT=$${BIFROST_PORT:-8000}"
	@echo "OTEL_EXPORTER_OTLP_ENDPOINT=$${OTEL_EXPORTER_OTLP_ENDPOINT:-http://host.docker.internal:4418}"
	@echo "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=$${OTEL_EXPORTER_OTLP_TRACES_ENDPOINT:-$${OTEL_EXPORTER_OTLP_ENDPOINT:-http://host.docker.internal:4418}/v1/traces}"
	@echo "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT=$${OTEL_EXPORTER_OTLP_METRICS_ENDPOINT:-$${OTEL_EXPORTER_OTLP_ENDPOINT:-http://host.docker.internal:4418}/v1/metrics}"
